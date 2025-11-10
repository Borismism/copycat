# Identity-Aware Proxy (IAP) Configuration
# Provides authentication and authorization for frontend service
# OAuth credentials stored in Secret Manager

# Enable IAP API
resource "google_project_service" "iap" {
  service            = "iap.googleapis.com"
  disable_on_destroy = false
}

data "google_project" "current" {
  project_id = var.project_id
}

# OAuth Brand (consent screen)
resource "google_iap_brand" "oauth_brand" {
  support_email     = var.iap_support_email
  application_title = "Copycat Management"
  project           = data.google_project.current.number

  depends_on = [google_project_service.iap]
}

# OAuth Client for IAP (EXTERNAL - manually created, DO NOT DESTROY)
# This is managed externally in Google Cloud Console and should NEVER be destroyed
# Credentials are stored in Secret Manager and must be set manually:
#
# gcloud secrets create iap-oauth-client-id --data-file=- <<EOF
# YOUR_CLIENT_ID_HERE
# EOF
#
# gcloud secrets create iap-oauth-client-secret --data-file=- <<EOF
# YOUR_CLIENT_SECRET_HERE
# EOF

# Store OAuth client ID in Secret Manager (create manually first)
data "google_secret_manager_secret_version" "iap_oauth_client_id" {
  secret  = "iap-oauth-client-id"
  project = var.project_id
}

# Store OAuth client secret in Secret Manager (create manually first)
data "google_secret_manager_secret_version" "iap_oauth_client_secret" {
  secret  = "iap-oauth-client-secret"
  project = var.project_id
}

locals {
  iap_client_id     = data.google_secret_manager_secret_version.iap_oauth_client_id.secret_data
  iap_client_secret = data.google_secret_manager_secret_version.iap_oauth_client_secret.secret_data
}

# Global static IP address for load balancer
resource "google_compute_global_address" "frontend_lb_ip" {
  name    = "copycat-frontend-lb-ip"
  project = var.project_id
}

# Managed SSL certificate
resource "random_id" "cert_suffix" {
  byte_length = 2
}

resource "google_compute_managed_ssl_certificate" "frontend_ssl_cert" {
  name = "copycat-frontend-ssl-cert-${random_id.cert_suffix.hex}"

  managed {
    domains = [var.frontend_domain]
  }

  project = var.project_id

  lifecycle {
    create_before_destroy = true
  }
}

# Serverless NEG for Cloud Run frontend service
resource "google_compute_region_network_endpoint_group" "frontend_neg" {
  name                  = "copycat-frontend-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  project               = var.project_id

  cloud_run {
    service = "frontend-service"
  }
}

# Backend service with IAP enabled
resource "google_compute_backend_service" "frontend_backend" {
  name                  = "copycat-frontend-backend"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  enable_cdn            = false
  project               = var.project_id

  backend {
    group = google_compute_region_network_endpoint_group.frontend_neg.id
  }

  iap {
    enabled              = true
    oauth2_client_id     = local.iap_client_id
    oauth2_client_secret = local.iap_client_secret
  }

  depends_on = [google_project_service.iap]
}

# URL map
resource "google_compute_url_map" "frontend_url_map" {
  name            = "copycat-frontend-url-map"
  default_service = google_compute_backend_service.frontend_backend.id
  project         = var.project_id
}

# HTTPS proxy
resource "google_compute_target_https_proxy" "frontend_https_proxy" {
  name             = "copycat-frontend-https-proxy"
  url_map          = google_compute_url_map.frontend_url_map.id
  ssl_certificates = [google_compute_managed_ssl_certificate.frontend_ssl_cert.id]
  project          = var.project_id
}

# Global forwarding rule (HTTPS)
resource "google_compute_global_forwarding_rule" "frontend_https_forwarding" {
  name                  = "copycat-frontend-https-forwarding"
  target                = google_compute_target_https_proxy.frontend_https_proxy.id
  ip_address            = google_compute_global_address.frontend_lb_ip.address
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  project               = var.project_id
}

# HTTP to HTTPS redirect
resource "google_compute_url_map" "http_redirect_url_map" {
  name    = "copycat-frontend-http-redirect-map"
  project = var.project_id

  default_url_redirect {
    https_redirect         = true
    strip_query            = false
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT" # 301 redirect
  }
}

resource "google_compute_target_http_proxy" "http_proxy" {
  name    = "copycat-frontend-http-proxy"
  url_map = google_compute_url_map.http_redirect_url_map.id
  project = var.project_id
}

resource "google_compute_global_forwarding_rule" "http_forwarding" {
  name                  = "copycat-frontend-http-forwarding"
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.http_proxy.id
  ip_address            = google_compute_global_address.frontend_lb_ip.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
  project               = var.project_id
}

# IAP access control - who can access the frontend
resource "google_iap_web_backend_service_iam_binding" "iap_users" {
  project             = var.project_id
  web_backend_service = google_compute_backend_service.frontend_backend.name
  role                = "roles/iap.httpsResourceAccessor"
  members             = var.iap_authorized_users
}
