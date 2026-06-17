terraform {
  backend "gcs" {
    bucket = "ctiq-terraform-state-data-eng-470620"
    prefix = "envs/dev"
  }
}
