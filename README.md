
# Быстрый старт

### Предварительные требования

1. Две VM с Ubuntu 22.04+ в одной сети (в примерах 192.168.56.0/24), рабочий пользователь на них в примерах будет указан как thomas
2. Настроенный Keycloak на ВМ 1 (см. [docs/keycloak-setup.md](docs/keycloak-setup))

# Шаг 1: Настройка ВМ 2 (Runtime + Gateway)

# Установка containerd и зависимостей
sudo apt update && sudo apt install -y containerd runc python3-pip python3-venv curl

### Установка CNI плагинов
CNI_VERSION="v1.4.0"
curl -LO https://github.com/containernetworking/plugins/releases/download/$CNI_VERSION/cni-plugins-linux-amd64-$CNI_VERSION.tgz
sudo mkdir -p /opt/cni/bin
sudo tar zxvf cni-plugins-linux-amd64-$CNI_VERSION.tgz -C /opt/cni/bin
rm -f cni-plugins-linux-amd64-$CNI_VERSION.tgz

### Установка crictl
CRICTL_VERSION="v1.29.0"
curl -LO https://github.com/kubernetes-sigs/cri-tools/releases/download/$CRICTL_VERSION/crictl-$CRICTL_VERSION-linux-amd64.tar.gz
sudo tar zxvf crictl-$CRICTL_VERSION-linux-amd64.tar.gz -C /usr/local/bin
rm -f crictl-$CRICTL_VERSION-linux-amd64.tar.gz

# Шаг 2: конфигурация

# CNI конфиг
sudo mkdir -p /etc/cni/net.d
sudo cp configs/10-bridge.conf /etc/cni/net.d/
sudo systemctl restart containerd

### Crictl конфиг
sudo cp configs/crictl.yaml /etc/crictl.yaml

### Sudo правило для crictl
echo "thomas ALL=(ALL) NOPASSWD: /usr/local/bin/crictl" | sudo tee /etc/sudoers.d/crictl
sudo chmod 440 /etc/sudoers.d/crictl

# Шаг 3: зависимости
cd ~
python3 -m venv gateway-env
source gateway-env/bin/activate
pip install -r requirements.txt

# Шаг 4: CLI helper

cp scripts/auth.sh ~/auth.sh
chmod +x ~/auth.sh

cat scripts/api_helper.sh >> ~/.bashrc
source ~/.bashrc

Шаг 5: Запуск
source ~/gateway-env/bin/activate
uvicorn gateway.main:app --host 0.0.0.0 --port 8080

## Управление контейнерами
### Создать контейнер
api POST /containers '{"image":"docker.io/library/busybox:latest"}'

### Просмотреть контейнеры
api GET /containers

### Удалить контейнер
api DELETE /containers/<container_id>

### CLI Helper (api-helper.sh)
Нужен для упрощения работы с API, благодаря ему и работают простые команды указанные выше
(Скрипт api_helper.sh необходимо добавить в конец файла ~/.bashrc и выполнить source ~/.bashrc).
