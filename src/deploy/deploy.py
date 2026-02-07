import paramiko
import os
import tarfile

DEFAULT_REMOTE_DIR = "/opt/easyinterview"
DEFAULT_DOMAIN = "easyinterview.oyemoye.top"
DEFAULT_EMAIL = "admin@oyemoye.top"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

def create_tar_gz(source_dirs, files, output_filename):
    """打包文件和目录"""
    print(f"Creating {output_filename}...")
    with tarfile.open(output_filename, "w:gz") as tar:
        for dir_name in source_dirs:
            dir_path = dir_name
            if not os.path.isabs(dir_path):
                dir_path = os.path.join(REPO_ROOT, dir_name)
            if os.path.exists(dir_path):
                tar.add(dir_path, arcname=dir_name)
        for file_name in files:
            file_path = file_name
            if not os.path.isabs(file_path):
                file_path = os.path.join(REPO_ROOT, file_name)
            if os.path.exists(file_path):
                tar.add(file_path, arcname=file_name)

def _env(name, default=None, required=False):
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value

def run_command(ssh, command, verbose=True):
    if verbose:
        print(f"Running: {command}")
    _, stdout, stderr = ssh.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors="replace").strip()
    err = stderr.read().decode(errors="replace").strip()
    if verbose and out:
        print(out)
    if err:
        print(err)
    return exit_status, out, err

def ensure_ok(result, message):
    code, _, _ = result
    if code != 0:
        raise RuntimeError(message)
    return result

def remote_has(ssh, binary):
    code, _, _ = run_command(ssh, f"command -v {binary}", verbose=False)
    return code == 0

def detect_pkg_manager(ssh):
    if remote_has(ssh, "apt-get"):
        return "apt"
    if remote_has(ssh, "dnf"):
        return "dnf"
    if remote_has(ssh, "yum"):
        return "yum"
    return None

def install_packages(ssh, pkg_mgr, packages):
    if pkg_mgr == "apt":
        ensure_ok(run_command(ssh, "DEBIAN_FRONTEND=noninteractive apt-get update"), "apt-get update failed")
        ensure_ok(
            run_command(
                ssh,
                "DEBIAN_FRONTEND=noninteractive apt-get install -y " + " ".join(packages),
            ),
            "apt-get install failed",
        )
        return
    if pkg_mgr in ("dnf", "yum"):
        ensure_ok(run_command(ssh, f"{pkg_mgr} makecache -y || true"), "repo cache failed")
        ensure_ok(run_command(ssh, f"{pkg_mgr} install -y " + " ".join(packages)), f"{pkg_mgr} install failed")
        return
    raise RuntimeError("No supported package manager found on remote host")

def deploy():
    package_path = os.path.join(BASE_DIR, "deploy_package.tar.gz")
    try:
        host = _env("DEPLOY_HOST", required=True)
        user = _env("DEPLOY_USER", "root")
        password = _env("DEPLOY_PASSWORD")
        key_path = _env("DEPLOY_KEY_PATH")
        remote_dir = _env("DEPLOY_REMOTE_DIR", DEFAULT_REMOTE_DIR)
        domain = _env("DEPLOY_DOMAIN", DEFAULT_DOMAIN)
        email = _env("DEPLOY_EMAIL", DEFAULT_EMAIL)
        include_env = _env("DEPLOY_INCLUDE_ENV", "1") == "1"

        package_files = ["app/requirements.txt", "deploy/easyinterview.service", "deploy/nginx_app.conf"]
        if include_env and os.path.exists(os.path.join(REPO_ROOT, ".env")):
            package_files.append(".env")
        elif include_env and os.path.exists(os.path.join(REPO_ROOT, "app", ".env")):
            package_files.append("app/.env")

        create_tar_gz(source_dirs=["app"], files=package_files, output_filename=package_path)

        print(f"Connecting to {host}...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs = {"hostname": host, "username": user, "timeout": 20}
        if key_path:
            connect_kwargs["key_filename"] = key_path
        elif password:
            connect_kwargs["password"] = password
        else:
            raise RuntimeError("Set DEPLOY_PASSWORD or DEPLOY_KEY_PATH for SSH auth")
        ssh.connect(**connect_kwargs)

        print("Installing base packages...")
        pkg_mgr = detect_pkg_manager(ssh)
        if pkg_mgr == "apt":
            install_packages(ssh, pkg_mgr, ["python3", "python3-venv", "python3-pip", "nginx", "certbot", "python3-certbot-nginx", "psmisc"])
        elif pkg_mgr in ("dnf", "yum"):
            install_packages(ssh, pkg_mgr, ["python3", "python3-pip", "nginx"])
            if not remote_has(ssh, "certbot"):
                run_command(ssh, f"{pkg_mgr} install -y epel-release || true")
                run_command(ssh, f"{pkg_mgr} install -y certbot python3-certbot-nginx || true")
        else:
            raise RuntimeError("Unsupported remote OS: no apt/dnf/yum found")

        ensure_ok(run_command(ssh, "systemctl enable --now nginx"), "failed to start nginx")

        ensure_ok(run_command(ssh, f"mkdir -p {remote_dir}"), "failed to create remote dir")
        ensure_ok(run_command(ssh, f"mkdir -p {remote_dir}/.tmp"), "failed to create tmp dir")

        print("Uploading package...")
        sftp = ssh.open_sftp()
        local_path = package_path
        remote_path = f"{remote_dir}/.tmp/deploy_package.tar.gz"
        sftp.put(local_path, remote_path)
        sftp.close()

        ensure_ok(run_command(ssh, f"rm -rf {remote_dir}/app {remote_dir}/deploy"), "failed to cleanup old release")

        print("Extracting files...")
        ensure_ok(run_command(ssh, f"cd {remote_dir} && tar -xzf {remote_dir}/.tmp/deploy_package.tar.gz"), "failed to extract package")

        if include_env:
            if remote_has(ssh, "bash"):
                run_command(ssh, f"test -f {remote_dir}/.env || test -f {remote_dir}/app/.env", verbose=False)

        run_command(ssh, "id -u easyinterview >/dev/null 2>&1 || useradd --system --create-home --home-dir /home/easyinterview --shell /usr/sbin/nologin easyinterview")
        ensure_ok(run_command(ssh, f"chown -R easyinterview:easyinterview {remote_dir}"), "failed to chown remote dir")

        print("Setting up virtual environment...")
        venv_path = f"{remote_dir}/venv"
        code, _, _ = run_command(ssh, f"test -d {venv_path}", verbose=False)
        if code != 0:
            ensure_ok(
                run_command(
                    ssh,
                    f"su -s /bin/bash -c 'python3 -m venv {venv_path}' easyinterview",
                ),
                "failed to create venv",
            )

        print("Installing dependencies...")
        ensure_ok(run_command(ssh, f"su -s /bin/bash -c '{venv_path}/bin/pip install -U pip' easyinterview"), "failed to upgrade pip")
        ensure_ok(run_command(ssh, f"su -s /bin/bash -c '{venv_path}/bin/pip install -r {remote_dir}/app/requirements.txt' easyinterview"), "failed to install requirements")

        print("Configuring systemd...")
        ensure_ok(run_command(ssh, f"cp {remote_dir}/deploy/easyinterview.service /etc/systemd/system/easyinterview.service"), "failed to copy systemd service")
        ensure_ok(run_command(ssh, "systemctl daemon-reload"), "systemctl daemon-reload failed")
        run_command(ssh, "systemctl stop easyinterview || true", verbose=False)
        run_command(ssh, "systemctl reset-failed easyinterview || true", verbose=False)
        run_command(ssh, "fuser -k 8000/tcp || true", verbose=False)
        ensure_ok(run_command(ssh, "systemctl enable --now easyinterview"), "failed to enable/start easyinterview")

        print("Configuring Nginx...")
        ensure_ok(run_command(ssh, "mkdir -p /var/www/html/.well-known/acme-challenge"), "failed to create webroot")
        if remote_has(ssh, "test"):
            code, _, _ = run_command(ssh, "test -d /etc/nginx/sites-available && test -d /etc/nginx/sites-enabled", verbose=False)
        else:
            code = 1
        if code == 0:
            site_name = domain
            run_command(ssh, f"rm -f /etc/nginx/sites-enabled/{domain} /etc/nginx/sites-available/{domain}", verbose=False)
            ensure_ok(run_command(ssh, f"cp {remote_dir}/deploy/nginx_app.conf /etc/nginx/sites-available/{site_name}"), "failed to copy nginx site")
            ensure_ok(run_command(ssh, f"ln -sf /etc/nginx/sites-available/{site_name} /etc/nginx/sites-enabled/{site_name}"), "failed to enable nginx site")
            run_command(ssh, "rm -f /etc/nginx/sites-enabled/default")
        else:
            ensure_ok(run_command(ssh, f"cp {remote_dir}/deploy/nginx_app.conf /etc/nginx/conf.d/{domain}.conf"), "failed to copy nginx conf.d")

        ensure_ok(run_command(ssh, "nginx -t"), "nginx -t failed")
        ensure_ok(run_command(ssh, "systemctl reload nginx"), "failed to reload nginx")

        print("Configuring firewall (best-effort)...")
        if remote_has(ssh, "ufw"):
            run_command(ssh, "ufw allow 'Nginx Full' || true")
        if remote_has(ssh, "firewall-cmd"):
            run_command(ssh, "firewall-cmd --permanent --add-service=http || true")
            run_command(ssh, "firewall-cmd --permanent --add-service=https || true")
            run_command(ssh, "firewall-cmd --reload || true")

        print(f"Requesting SSL certificate for {domain}...")
        if remote_has(ssh, "certbot"):
            certbot_cmd = (
                f"certbot --nginx -d {domain} "
                f"-m {email} --agree-tos --no-eff-email --redirect --non-interactive"
            )
            code, _, _ = run_command(ssh, certbot_cmd)
            if code != 0:
                raise RuntimeError("certbot failed; check DNS/80 port and /var/log/letsencrypt/letsencrypt.log")
            ensure_ok(run_command(ssh, "systemctl reload nginx"), "failed to reload nginx after certbot")
        else:
            raise RuntimeError("certbot is not installed on the server")

        print("Verifying services...")
        run_command(ssh, "systemctl --no-pager -l status easyinterview | tail -n 50 || true")
        run_command(ssh, f"curl -I -m 10 http://127.0.0.1:8000/ | head -n 20 || true")
        run_command(ssh, f"curl -I -m 10 https://{domain}/ | head -n 20 || true")

        print(f"Deployment complete: https://{domain}")

        ssh.close()
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # 清理
        if os.path.exists(package_path):
            os.remove(package_path)

if __name__ == "__main__":
    deploy()
