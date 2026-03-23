#!/bin/bash

# DDD Weather Discount - Reference Solution
# This script applies the reference solution to the project.

set -e

cd /app

# -------------------------------------------------------------------
# 1. Create WeatherService infrastructure (anti-corruption layer)
# -------------------------------------------------------------------

INFRA_DIR="Sources/Sales/Sales.Adapters/Weather"
mkdir -p "$INFRA_DIR"

cat > "$INFRA_DIR/OpenMeteoWeatherService.cs" << 'EOF'
using System.Net.Http.Json;
using System.Text.Json.Serialization;

namespace MyCompany.ECommerce.Sales.Adapters.Weather;

public interface IWeatherService
{
    Task<WeatherData> GetCurrentWeatherAsync();
}

public record WeatherData(decimal Precipitation);

public class OpenMeteoWeatherService : IWeatherService
{
    private static readonly HttpClient HttpClient = new();
    private const string ApiUrl = "https://api.open-meteo.com/v1/forecast?latitude=52.2297&longitude=21.0122&current=precipitation";

    public async Task<WeatherData> GetCurrentWeatherAsync()
    {
        try
        {
            var response = await HttpClient.GetFromJsonAsync<OpenMeteoResponse>(ApiUrl);
            return new WeatherData(response?.Current?.Precipitation ?? 0);
        }
        catch
        {
            return new WeatherData(0);
        }
    }

    private record OpenMeteoResponse
    {
        [JsonPropertyName("current")]
        public CurrentData? Current { get; init; }
    }

    private record CurrentData
    {
        [JsonPropertyName("precipitation")]
        public decimal Precipitation { get; init; }
    }
}
EOF

echo "✓ OpenMeteoWeatherService.cs created"

# -------------------------------------------------------------------
# 2. Create WeatherDiscount value object
# -------------------------------------------------------------------

DISCOUNT_DIR="Sources/Sales/Sales.DeepModel/Pricing/Discounts"

cat > "$DISCOUNT_DIR/WeatherDiscount.cs" << 'EOF'
using MyCompany.ECommerce.Sales.Commons;

namespace MyCompany.ECommerce.Sales.Pricing.Discounts;

public readonly struct WeatherDiscount : PriceModifier, IEquatable<WeatherDiscount>
{
    private readonly PercentageDiscount _discount;
    private readonly bool _isActive;

    private WeatherDiscount(PercentageDiscount discount, bool isActive)
    {
        _discount = discount;
        _isActive = isActive;
    }

    public static WeatherDiscount Active(Percentage discountValue) =>
        new(PercentageDiscount.Of(discountValue), true);

    public static WeatherDiscount Inactive() =>
        new(default, false);

    public Money ApplyOn(Money price) =>
        _isActive ? _discount.ApplyOn(price) : price;

    public bool Equals(WeatherDiscount other) =>
        _discount.Equals(other._discount) && _isActive == other._isActive;

    public override bool Equals(object? obj) =>
        obj is WeatherDiscount other && Equals(other);

    public override int GetHashCode() =>
        HashCode.Combine(_discount, _isActive);

    public static bool operator ==(WeatherDiscount left, WeatherDiscount right) =>
        left.Equals(right);

    public static bool operator !=(WeatherDiscount left, WeatherDiscount right) =>
        !left.Equals(right);

    public override string ToString() =>
        _isActive ? $"Weather {_discount}" : "Weather (inactive)";
}
EOF

echo "✓ WeatherDiscount.cs created"

# -------------------------------------------------------------------
# 3. Extend Discount discriminated union with weather variant
# -------------------------------------------------------------------

# Rewrite Discount.cs entirely — sed patches are fragile on readonly structs
DISCOUNT_FILE="Sources/Sales/Sales.DeepModel/Pricing/Discounts/Discount.cs"

cat > "$DISCOUNT_FILE" << 'EOF'
using MyCompany.ECommerce.Sales.Commons;
using NoesisVision.Annotations.Domain.DDD;

namespace MyCompany.ECommerce.Sales.Pricing.Discounts;

[DddValueObject]
public readonly struct Discount : PriceModifier, IEquatable<Discount>
{
    private readonly bool _isPercentage;
    private readonly bool _isWeather;
    private readonly PercentageDiscount _percentageDiscount;
    private readonly ValueDiscount _valueDiscount;
    private readonly WeatherDiscount _weatherDiscount;

    public static Discount Percentage(Percentage value) =>
        new(isPercentage: true, isWeather: false, PercentageDiscount.Of(value), default, default);

    public static Discount Value(Money value) =>
        new(isPercentage: false, isWeather: false, default, ValueDiscount.Of(value), default);

    public static Discount Weather(WeatherDiscount weatherDiscount) =>
        new(isPercentage: false, isWeather: true, default, default, weatherDiscount);

    private Discount(
        bool isPercentage,
        bool isWeather,
        PercentageDiscount percentageDiscount,
        ValueDiscount valueDiscount,
        WeatherDiscount weatherDiscount)
    {
        _isPercentage = isPercentage;
        _isWeather = isWeather;
        _percentageDiscount = percentageDiscount;
        _valueDiscount = valueDiscount;
        _weatherDiscount = weatherDiscount;
    }

    public Money ApplyOn(Money price) => _isWeather
        ? _weatherDiscount.ApplyOn(price)
        : _isPercentage
            ? _percentageDiscount.ApplyOn(price)
            : _valueDiscount.ApplyOn(price);

    public bool Equals(Discount other) =>
        (_isPercentage, _isWeather, _percentageDiscount, _valueDiscount, _weatherDiscount)
            .Equals((other._isPercentage, other._isWeather, other._percentageDiscount, other._valueDiscount, other._weatherDiscount));

    public override bool Equals(object? obj) => obj is Discount other && Equals(other);
    public override int GetHashCode() =>
        (_isPercentage, _isWeather, _percentageDiscount, _valueDiscount, _weatherDiscount).GetHashCode();

    public override string ToString() => _isWeather
        ? _weatherDiscount.ToString()
        : _isPercentage
            ? _percentageDiscount.ToString()
            : _valueDiscount.ToString();
}
EOF

echo "✓ Discount.cs extended with weather variant"

echo ""
echo "Reference solution applied successfully."
echo "Run 'dotnet build && dotnet test' to verify."
