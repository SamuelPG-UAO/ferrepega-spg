#!/bin/bash
# =========================================================
# Ferrepega - Aprovisionamiento del servidor BACK
# Paso 2: instala PostgreSQL y crea las 4 bases de datos
# Paso 3: instala Python, entorno virtual y librerías
# Paso 8: gateway Nginx y servicios systemd (gateway.sh)
# Se puede ejecutar varias veces sin romper nada (idempotente)
# =========================================================

# Si cualquier comando falla, el script se detiene
set -e

# Evita que apt haga preguntas interactivas durante la instalación
export DEBIAN_FRONTEND=noninteractive

# Nos movemos a /tmp para que el usuario "postgres" pueda ejecutar psql
# sin quejarse de que no puede entrar a la carpeta actual
cd /tmp

echo ">>> [1/5] Actualizando lista de paquetes..."
apt-get update -y

echo ">>> [2/5] Instalando PostgreSQL..."
apt-get install -y postgresql postgresql-contrib

echo ">>> [3/5] Habilitando y arrancando el servicio..."
systemctl enable postgresql
systemctl start postgresql

echo ">>> [4/5] Creando usuarios y bases de datos..."

# Función: crea un usuario y una base de datos que le pertenece,
# solo si todavía no existen.
#   $1 = nombre de la base de datos
#   $2 = nombre del usuario
#   $3 = contraseña del usuario
crear_bd() {
  local bd="$1"
  local usuario="$2"
  local clave="$3"

  # Crear el usuario (rol) si no existe
  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${usuario}'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE ROLE ${usuario} LOGIN PASSWORD '${clave}';"
  fi

  # Crear la base de datos si no existe, con ese usuario como dueño
  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${bd}'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE DATABASE ${bd} OWNER ${usuario};"
  fi

  # Aislamiento: nadie más puede conectarse a esta base de datos,
  # solo su dueño (y el superusuario postgres)
  sudo -u postgres psql -c "REVOKE CONNECT ON DATABASE ${bd} FROM PUBLIC;"
  sudo -u postgres psql -c "GRANT CONNECT ON DATABASE ${bd} TO ${usuario};"
}

# Una base de datos y un usuario por microservicio
crear_bd "auth_db"       "auth_user"       "Ferre_auth_2025"
crear_bd "inventario_db" "inventario_user" "Ferre_inventario_2025"
crear_bd "ventas_db"     "ventas_user"     "Ferre_ventas_2025"
crear_bd "analitica_db"  "analitica_user"  "Ferre_analitica_2025"

echo ">>> Bases de datos creadas:"
sudo -u postgres psql -lqt | cut -d '|' -f 1 | grep -E '_db' || true

echo ">>> [5/5] Instalando Python, entorno virtual y librerías..."
apt-get install -y python3 python3-venv python3-pip

# El entorno virtual vive en la carpeta personal del usuario vagrant
# y NO dentro de /vagrant: esa carpeta es compartida con Windows y
# ahí los entornos virtuales pueden fallar al crear enlaces simbólicos.
if [ ! -d /home/vagrant/venv ]; then
  sudo -u vagrant python3 -m venv /home/vagrant/venv
fi
sudo -u vagrant /home/vagrant/venv/bin/pip install --upgrade pip

if [ -f /vagrant/datos/requirements.txt ]; then
  sudo -u vagrant /home/vagrant/venv/bin/pip install -r /vagrant/datos/requirements.txt
else
  echo "AVISO: no se encontró /vagrant/datos/requirements.txt, no se instalaron librerías."
fi

# Activar el entorno virtual automáticamente al entrar por SSH
if ! grep -q "venv/bin/activate" /home/vagrant/.bashrc; then
  echo 'source /home/vagrant/venv/bin/activate' >> /home/vagrant/.bashrc
fi

echo ">>> Listo. Python instalado:"
/home/vagrant/venv/bin/python --version

# Paso 8: gateway Nginx + microservicios como servicios de systemd.
# Si falla (por ejemplo, porque aún no existe el código del backend), el
# aprovisionamiento base ya quedó hecho y se puede repetir con:
#     sudo bash /vagrant/aprovisionamiento/gateway.sh
if [ -d /vagrant/backend ]; then
  bash /vagrant/aprovisionamiento/gateway.sh || echo "AVISO: gateway.sh terminó con errores; revísalos arriba."
fi
