FROM mcr.microsoft.com/dotnet/sdk:8.0

RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Use the "dotnet6" branch: it is the SDK-style, modern-hosting port of the
# "Online Theater" sample. The default `master` branch is legacy .NET Framework
# 4.6.2 with old-style csproj + net40 NHibernate binaries, which does NOT build on
# the Linux dotnet/sdk image. The dotnet6 branch uses NuGet FluentNHibernate 3.1.0 /
# NHibernate 5.3.12 / System.Data.SqlClient — all build on Linux with no database.
RUN git clone --depth 1 --branch dotnet6 https://github.com/vkhorikov/AnemicDomainModel.git .

# The agent works on the anemic "Before" solution.
WORKDIR /app/Before

# Upgrade the target framework from net6.0 to net8.0. The dotnet/sdk:8.0 image
# ships only the net8.0 targeting pack, so the original net6.0 TFM would fail to
# restore. NHibernate / FluentNHibernate / Newtonsoft.Json are netstandard2.0 and
# work unchanged on net8.0.
RUN find . -name '*.csproj' -exec sed -i 's/net6\.0/net8.0/g' {} +

# NOTE: NHibernate connects to SQL Server only at RUNTIME (SessionFactory builds a
# session lazily). Compiling and unit-testing the domain model requires NO running
# database, so the image is build-only — no SQL Server sidecar.
RUN dotnet restore OnlineTheaterBefore.sln
RUN dotnet build OnlineTheaterBefore.sln --no-restore

CMD ["/bin/bash"]
