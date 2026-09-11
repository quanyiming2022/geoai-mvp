#!/usr/bin/env bash
# Host prerequisites only. Run manually with sudo after reviewing.
# Sources: docs.docker.com/engine/install/ubuntu/
# docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo 'Run this script with sudo.' >&2; exit 1; fi
geoai_user=${SUDO_USER:-}
if [[ -z "$geoai_user" || "$geoai_user" == root ]]; then echo 'Run sudo from the deployment user account.' >&2; exit 1; fi
. /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 && $(dpkg --print-architecture) == amd64 ]] || { echo 'Expected Ubuntu 24.04 amd64'; exit 1; }
# Do not remove or replace existing container installations.
for package in docker.io podman-docker containerd runc; do
  if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
    echo "Existing $package detected. Stop for review." >&2; exit 1
  fi
done
apt-get update
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
geoai_tmp=$(mktemp -d)
trap 'rm -rf "$geoai_tmp"' EXIT
curl --connect-timeout 15 --max-time 120 -fsSL https://download.docker.com/linux/ubuntu/gpg -o "$geoai_tmp/docker.asc"
install -m 0644 "$geoai_tmp/docker.asc" /etc/apt/keyrings/docker.asc
cat > "$geoai_tmp/docker.sources" <<'EOF'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
if [[ -e /etc/apt/sources.list.d/docker.sources ]] && ! cmp -s "$geoai_tmp/docker.sources" /etc/apt/sources.list.d/docker.sources; then echo 'Existing Docker source differs; stop for review.'; exit 1; fi
install -m 0644 "$geoai_tmp/docker.sources" /etc/apt/sources.list.d/docker.sources
curl --connect-timeout 15 --max-time 120 -fsSL https://nvidia.github.io/libnvidia-container/gpgkey -o "$geoai_tmp/nvidia.asc"
gpg --batch --dearmor -o "$geoai_tmp/nvidia.gpg" "$geoai_tmp/nvidia.asc"
install -m 0644 "$geoai_tmp/nvidia.gpg" /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl --connect-timeout 15 --max-time 120 -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list -o "$geoai_tmp/nvidia.list"
sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' "$geoai_tmp/nvidia.list" > "$geoai_tmp/nvidia-signed.list"
if [[ -e /etc/apt/sources.list.d/nvidia-container-toolkit.list ]] && ! cmp -s "$geoai_tmp/nvidia-signed.list" /etc/apt/sources.list.d/nvidia-container-toolkit.list; then echo 'Existing NVIDIA source differs; stop for review.'; exit 1; fi
install -m 0644 "$geoai_tmp/nvidia-signed.list" /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin nvidia-container-toolkit
if [[ -f /etc/docker/daemon.json ]]; then cp -a /etc/docker/daemon.json "/etc/docker/daemon.json.geoai-backup-$(date +%s)"; fi
nvidia-ctk runtime configure --runtime=docker
systemctl enable --now docker
systemctl restart docker
# Docker group grants host-administrator-equivalent privileges; no sudoers edits.
usermod -aG docker "$geoai_user"
docker version
docker compose version
nvidia-ctk --version
docker run --rm --gpus device=1 ubuntu:24.04 nvidia-smi
echo 'Host prerequisites installed. Log out and reconnect to refresh Docker group membership.'
