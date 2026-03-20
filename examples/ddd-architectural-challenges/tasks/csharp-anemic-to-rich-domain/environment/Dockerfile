FROM mcr.microsoft.com/dotnet/sdk:6.0

RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/kgrzybek/refactoring-from-anemic-to-rich-domain-model-example.git . && git checkout anemic

# Upgrade project from netcoreapp2.2 to net6.0
RUN sed -i 's/netcoreapp2.2/net6.0/' DotNetConfPl.Refactoring/DotNetConfPl.Refactoring.csproj && \
    sed -i 's/<PackageReference Include="Microsoft.AspNetCore.App" \/>//' DotNetConfPl.Refactoring/DotNetConfPl.Refactoring.csproj && \
    sed -i 's/<PackageReference Include="Microsoft.AspNetCore.Razor.Design" Version="2.2.0" PrivateAssets="All" \/>//' DotNetConfPl.Refactoring/DotNetConfPl.Refactoring.csproj && \
    sed -i 's/Version="2.2.6"/Version="6.0.0"/g' DotNetConfPl.Refactoring/DotNetConfPl.Refactoring.csproj && \
    sed -i 's/Version="4.0.1"/Version="6.5.0"/g' DotNetConfPl.Refactoring/DotNetConfPl.Refactoring.csproj

# Fix Swagger for .NET 6 (DescribeAllEnumsAsStrings removed, Info -> OpenApiInfo)
RUN sed -i '/DescribeAllEnumsAsStrings/d' DotNetConfPl.Refactoring/Startup.cs && \
    sed -i 's/Swashbuckle.AspNetCore.Swagger.Info/Microsoft.OpenApi.Models.OpenApiInfo/g' DotNetConfPl.Refactoring/Startup.cs && \
    sed -i '1s/^/using Microsoft.OpenApi.Models;\n/' DotNetConfPl.Refactoring/Startup.cs

RUN dotnet restore DotNetConfPl.Refactoring/DotNetConfPl.Refactoring.csproj
RUN dotnet build DotNetConfPl.Refactoring/DotNetConfPl.Refactoring.csproj --no-restore

CMD ["/bin/bash"]
