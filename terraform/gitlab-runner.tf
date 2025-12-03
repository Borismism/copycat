# GitLab Runner on GCP - Spot/Preemptible VM for cost savings
# Runs CI/CD jobs for the copycat project

resource "google_compute_instance" "gitlab_runner" {
  name         = "gitlab-runner"
  machine_type = "e2-small"  # 2 vCPU, 2GB RAM - enough for CI/CD
  zone         = "${var.region}-a"
  project      = var.project_id

  # Spot VM - 60-91% cheaper than regular
  scheduling {
    preemptible                 = true
    automatic_restart           = false
    provisioning_model          = "SPOT"
    instance_termination_action = "STOP"
  }

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 30  # GB - enough for docker images
      type  = "pd-standard"  # Standard disk is cheaper
    }
  }

  network_interface {
    network = "default"
    access_config {
      # Ephemeral public IP
    }
  }

  # Startup script to install GitLab Runner and Docker
  metadata_startup_script = <<-EOF
    #!/bin/bash
    set -e

    # Install Docker
    apt-get update
    apt-get install -y apt-transport-https ca-certificates curl software-properties-common
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
    add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io

    # Install GitLab Runner
    curl -L https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.deb.sh | bash
    apt-get install -y gitlab-runner

    # Add gitlab-runner to docker group
    usermod -aG docker gitlab-runner

    # Create registration script (needs manual token)
    cat > /home/gitlab-runner/register.sh << 'SCRIPT'
    #!/bin/bash
    # Run this with: sudo bash /home/gitlab-runner/register.sh <REGISTRATION_TOKEN>
    gitlab-runner register \
      --non-interactive \
      --url "https://code.irdeto.com" \
      --registration-token "$1" \
      --executor "docker" \
      --docker-image "google/cloud-sdk:slim" \
      --description "copycat-runner-gcp" \
      --tag-list "gcp,docker,copycat" \
      --run-untagged="true" \
      --locked="false"
    SCRIPT
    chmod +x /home/gitlab-runner/register.sh

    echo "GitLab Runner installed. Register with: sudo bash /home/gitlab-runner/register.sh <TOKEN>"
  EOF

  tags = ["gitlab-runner", "allow-ssh"]

  service_account {
    email  = google_service_account.gitlab_ci_deployer.email
    scopes = ["cloud-platform"]
  }

  labels = {
    purpose = "gitlab-runner"
    env     = var.environment
  }
}

# Firewall rule to allow SSH
resource "google_compute_firewall" "gitlab_runner_ssh" {
  name    = "gitlab-runner-allow-ssh"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["allow-ssh"]
}

output "gitlab_runner_ip" {
  value       = google_compute_instance.gitlab_runner.network_interface[0].access_config[0].nat_ip
  description = "GitLab Runner public IP"
}

output "gitlab_runner_ssh_command" {
  value       = "gcloud compute ssh gitlab-runner --zone=${google_compute_instance.gitlab_runner.zone} --project=${var.project_id}"
  description = "SSH to the runner VM"
}
