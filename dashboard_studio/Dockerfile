# syntax=docker/dockerfile:1

# Stage 1: frontend build. Pinned to --platform=$BUILDPLATFORM so this stage
# runs once on the build host and is shared across every target arch in the
# buildx multi-arch build below -- JS build output is arch-agnostic, so
# there's no reason to pay for it under aarch64 QEMU emulation.
FROM --platform=$BUILDPLATFORM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: runtime. This IS built per target platform by buildx.
# No build.yaml (deprecated since Supervisor 2026.04.0) -- this FROM is the
# single source of truth for the base image, matching HA's current
# "Dockerfile is authoritative" build model.
FROM ghcr.io/home-assistant/base-python:3.12
WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/src ./src

# The built frontend must land inside the package directory *before* `pip
# install .` builds the wheel, so hatchling's default file selection packs
# it in as package data. There's no .git here for hatchling's VCS-based file
# listing to consult, so it falls back to "include everything under
# packages/" -- which is exactly what we want for the static/ directory.
COPY --from=frontend-builder /app/dist ./src/dashboard_studio/static

RUN pip install --no-cache-dir .

COPY rootfs /

# base-python already ships s6-overlay v3 as the image entrypoint; our
# service script under /etc/s6-overlay/s6-rc.d is what actually gets
# supervised and started (see rootfs/etc/s6-overlay/s6-rc.d/dashboard_studio/run).
