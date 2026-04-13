FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99

# Install OpenROAD dependencies + display tools
RUN apt-get update && apt-get install -y \
    wget \
    libboost-all-dev \
    tcl-dev \
    libgomp1 \
    libpython3.10 \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    libxcb-xinerama0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install OpenROAD prebuilt binary
RUN wget https://github.com/The-OpenROAD-Project/OpenROAD/releases/download/v2.0-18118/openroad_Ubuntu22.04_amd64.tar.gz \
    -O /tmp/openroad.tar.gz \
    && tar -xzf /tmp/openroad.tar.gz -C /usr/local --strip-components=1 \
    && rm /tmp/openroad.tar.gz

WORKDIR /workspace
