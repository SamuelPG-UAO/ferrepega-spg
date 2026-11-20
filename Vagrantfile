# -*- mode: ruby -*-
# vi: set ft=ruby :
#
# Ferrepega - Infraestructura con Vagrant + VirtualBox
# Define dos servidores: ferrepega-back y ferrepega-front

Vagrant.configure("2") do |config|
config.vm.boot_timeout = 900

  # Imagen base (Ubuntu 22.04 LTS) compatible con VirtualBox
  config.vm.box = "ubuntu/jammy64"

  # ---------------------------------------------------------
  # SERVIDOR BACK: Nginx (gateway), microservicios, PostgreSQL
  # ---------------------------------------------------------
  config.vm.define "back" do |back|
    back.vm.hostname = "ferrepega-back"
    back.vm.network "private_network", ip: "192.168.56.10"

    back.vm.provider "virtualbox" do |vb|
      vb.name   = "ferrepega-back"
      # Entrega final: aquí corren Docker Swarm (manager), PostgreSQL, Prometheus,
      # Grafana y parte de Spark, así que necesita más memoria que antes (2048).
      vb.memory = 4096
      vb.cpus   = 2
    end

    # Script de instalación: PostgreSQL y bases de datos
    back.vm.provision "shell", path: "aprovisionamiento/back.sh"
  end

  # ---------------------------------------------------------
  # SERVIDOR FRONT: Nginx + Flask (interfaz web)
  # ---------------------------------------------------------
  config.vm.define "front" do |front|
    front.vm.hostname = "ferrepega-front"
    front.vm.network "private_network", ip: "192.168.56.11"

    front.vm.provider "virtualbox" do |vb|
      vb.name   = "ferrepega-front"
      # Entrega final: nodo trabajador de Swarm (réplicas de servicios y workers de Spark)
      vb.memory = 3584
      vb.cpus   = 2
    end

    # Se activará en el siguiente paso, cuando creemos el script
    # front.vm.provision "shell", path: "aprovisionamiento/front.sh"
  end

end
