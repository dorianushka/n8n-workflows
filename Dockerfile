FROM n8nio/n8n:latest

USER root

# Install Python and pip (n8n image is Alpine-based)
RUN apk add --update --no-cache python3 py3-pip

# Install your Python dependencies (e.g., discord.py; add more if needed)
# Use --break-system-packages to bypass external management warning on Alpine
RUN pip3 install --break-system-packages discord.py

# Switch back to n8n's default user
USER node