# DDD Weather Discount Challenge - Environment Setup
FROM mcr.microsoft.com/dotnet/sdk:8.0

# Prevent MSBuild worker-node fleets from accumulating across the agent's repeated
# build/test cycles (default nodeReuse keeps ~1 node per core alive for 15 min;
# three generations of fleets OOM-killed heavy trials at the 6 GiB cgroup limit -
# see kernel memcg OOM reports, 2026-07-10). Nodes now exit with each build.
ENV MSBUILDDISABLENODEREUSE=1
ENV DOTNET_CLI_USE_MSBUILD_SERVER=0

# Install essential tools
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Clone the DDD-starter-dotnet repository into /app
WORKDIR /app
RUN git clone https://github.com/itlibrium/DDD-starter-dotnet.git .

# Restore dependencies and perform initial build
# This ensures all NuGet packages are downloaded and the project is buildable
RUN dotnet restore MyCompany.ECommerce.sln
RUN dotnet build MyCompany.ECommerce.sln --configuration Debug --no-restore

# Verify build succeeded
RUN echo "Build verification completed successfully"

# Default command
CMD ["/bin/bash"]
