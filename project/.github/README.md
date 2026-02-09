# GitHub Actions CI/CD Setup

## Overview
This directory contains GitHub Actions workflows for automated CI/CD.

## Files
- `.github/workflows/ci.yml` - Main CI/CD pipeline

## Pipeline Stages

### 1. Lint
- Ruff linter
- Black code formatter check
- Import sorting check

### 2. Test
- pytest with coverage
- Upload to Codecov

### 3. Build
- Docker build with Buildx
- Push to GHCR (GitHub Container Registry)
- Multi-platform support

### 4. Deploy
- Update ArgoCD application
- GitOps-based deployment

## Usage

### Triggers
- Push to `main` or `develop` branches
- Pull requests to `main`

### Required Secrets
- `GITHUB_TOKEN` - Automatically available
- `SLACK_WEBHOOK` - For notifications (optional)

### Setup
1. Push this directory to GitHub
2. Enable GitHub Actions
3. Set up ArgoCD to sync from this repo

## Docker Image
- Registry: `ghcr.io/your-org/shadowdesk`
- Tag: Latest commit SHA
