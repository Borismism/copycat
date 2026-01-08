# GitLab Runner on GCP - Spot/Preemptible VM for cost savings
# Runs CI/CD jobs for the copycat project
# Auto-registers on boot using token from Secret Manager

# =============================================================================
# Secret Manager for GitLab Runner Token
# =============================================================================
resource "google_secret_manager_secret" "gitlab_runner_token" {
  secret_id = "gitlab-runner-token"
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    service    = "copycat"
    managed_by = "terraform"
  }

  depends_on = [google_project_service.apis]
}

# Grant the runner service account access to read the token
resource "google_secret_manager_secret_iam_member" "gitlab_runner_token_access" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.gitlab_runner_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.gitlab_ci_deployer.email}"
}

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

  # Startup script to install GitLab Runner, Docker, and auto-register
  metadata_startup_script = <<-EOF
    #!/bin/bash
    set -e

    LOG_FILE="/var/log/gitlab-runner-setup.log"
    exec > >(tee -a $LOG_FILE) 2>&1
    echo "=== GitLab Runner setup started at $(date) ==="

    # Install Docker (using new GPG keyring approach)
    if ! command -v docker &> /dev/null; then
      echo "Installing Docker..."
      apt-get update
      apt-get install -y apt-transport-https ca-certificates curl software-properties-common

      install -m 0755 -d /etc/apt/keyrings
      curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
      chmod a+r /etc/apt/keyrings/docker.asc

      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

      apt-get update
      apt-get install -y docker-ce docker-ce-cli containerd.io
      echo "Docker installed successfully"
    else
      echo "Docker already installed"
    fi

    # Install GitLab Runner
    if ! command -v gitlab-runner &> /dev/null; then
      echo "Installing GitLab Runner..."
      curl -L https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.deb.sh | bash
      apt-get install -y gitlab-runner
      usermod -aG docker gitlab-runner
      echo "GitLab Runner installed successfully"
    else
      echo "GitLab Runner already installed"
    fi

    # Auto-register runner using token from Secret Manager
    echo "Checking runner registration..."
    if ! gitlab-runner list 2>&1 | grep -q "copycat-runner-gcp"; then
      echo "Fetching token from Secret Manager..."

      # Get token from Secret Manager
      TOKEN=$(gcloud secrets versions access latest --secret=gitlab-runner-token --project=${var.project_id} 2>/dev/null || echo "")

      if [ -z "$TOKEN" ]; then
        echo "ERROR: Could not fetch GitLab runner token from Secret Manager"
        echo "Please add the token: gcloud secrets versions add gitlab-runner-token --data-file=- --project=${var.project_id}"
        exit 1
      fi

      echo "Registering runner with GitLab..."
      gitlab-runner register \
        --non-interactive \
        --url "https://code.irdeto.com" \
        --token "$TOKEN" \
        --executor "docker" \
        --docker-image "google/cloud-sdk:slim" \
        --description "copycat-runner-gcp"

      echo "Runner registered successfully"
    else
      echo "Runner already registered, verifying..."
      gitlab-runner verify
    fi

    # Ensure runner service is running
    systemctl enable gitlab-runner
    systemctl restart gitlab-runner

    echo "=== GitLab Runner setup completed at $(date) ==="
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

  depends_on = [google_secret_manager_secret_iam_member.gitlab_runner_token_access]
}

# Firewall rule to allow SSH via IAP only (secure - no public SSH)
resource "google_compute_firewall" "gitlab_runner_ssh" {
  name    = "gitlab-runner-allow-ssh-iap"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # IAP's IP range - only allows SSH through IAP tunnel
  source_ranges = ["35.235.240.0/20"]

  # Target only the gitlab runner service account
  target_service_accounts = [google_service_account.gitlab_ci_deployer.email]
}

# IAM binding for IAP tunnel access - only deployer SA can SSH
resource "google_iap_tunnel_instance_iam_member" "gitlab_runner_ssh_access" {
  project  = var.project_id
  zone     = google_compute_instance.gitlab_runner.zone
  instance = google_compute_instance.gitlab_runner.name
  role     = "roles/iap.tunnelResourceAccessor"
  member   = "serviceAccount:${google_service_account.gitlab_ci_deployer.email}"
}

output "gitlab_runner_ip" {
  value       = google_compute_instance.gitlab_runner.network_interface[0].access_config[0].nat_ip
  description = "GitLab Runner public IP"
}

output "gitlab_runner_ssh_command" {
  value       = "gcloud compute ssh gitlab-runner --zone=${google_compute_instance.gitlab_runner.zone} --project=${var.project_id}"
  description = "SSH to the runner VM"
}

output "gitlab_runner_token_setup_command" {
  value       = "echo 'YOUR_GITLAB_RUNNER_TOKEN' | gcloud secrets versions add gitlab-runner-token --data-file=- --project=${var.project_id}"
  description = "Command to store the GitLab runner token in Secret Manager"
}
