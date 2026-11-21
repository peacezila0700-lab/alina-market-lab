#include <Math/Stat/Math.mqh>
#include <Trade/SymbolInfo.mqh>

namespace FxceSymbol
{
    /**
     * @brief Calculate volume for order.
     * 
     * @param entry Entry point.
     * @param sl Stop loss point.
     * @param risk Money for risk.
     * @param symbol Input symbol.
     * @param normalizable Able to be normalized.
     * @return Volume of risk. If entry = stop loss or symbol is not available in market watch, return 0.
     */
    double CalculateVolume(const double entry, const double sl, const double risk, const string symbol = NULL, const bool normalizable = true)
    {
        long riskPeriod = RiskPeriod(entry, sl, symbol);
        if (riskPeriod <= 0)
        {
            return 0;
        }

       return CalculateVolume(riskPeriod, risk, symbol, normalizable);
    }
    /**
     * @brief Calculate volume for order.
     * 
     * @param riskPeriod Risk points.
     * @param risk Money for risk.
     * @param symbol Input symbol.
     * @param normalizable Able to be normalized.
     * @return Volume of risk. If symbol is not available in market watch, return 0.
     */
    double CalculateVolume(const ulong riskPeriod, const double risk, const string symbol = NULL, const bool normalizable = true)
    {
        double pointValue = PointValue();
        double volume = risk / (riskPeriod * pointValue);
        if (normalizable)
        {
            return NormalizeVolume(volume);
        }

        return volume;
    }
    /**
     * @brief Normalize volume with volume step's digits of symbol
     * 
     * @param volume Input Volume to normalize.
     * @param symbol Input Symbol. In case of NULL means current symbol.
     * @return Normalized volume. If symbol is not available in market watch, return 0.
     */
    double NormalizeVolume(const double volume, const string symbol = NULL)
    {
        CSymbolInfo info;
        if (info.Name(symbol))
        {
            int digits = VolumeDigits(symbol);
            double temp = MathRound(volume, digits);
            return temp;
        }

        return 0;
    }
    /**
     * @brief Get the volume step's digits of symbol
     * 
     * @param symbol Input Symbol. In case of NULL means current symbol.
     * @return volume digits. If symbol is not available in market watch, return 0.
     */
    int VolumeDigits(const string symbol = NULL)
    {
        CSymbolInfo info;
        if (info.Name(symbol))
        {
            double step = info.LotsStep();
            return MathAbs(MathLog10(step));
        }

        return 0;
    }
    /**
     * @brief Calculate point value of symbol
     * 
     * @param symbol Input Symbol. In case of NULL means current symbol.
     * @return Point value, If symbol is not available in market watch, return 0
     */
    double PointValue(const string symbol = NULL)
    {
        CSymbolInfo info;
        if (info.Name(symbol))
        {
            double point = info.Point();
            double tickValue = info.TickValue();
            double tickSize = info.TickSize();
            double pointValue = tickValue * point / tickSize;
            return pointValue;
        }

        return 0;
    }
    /**
    * @brief Normalize price with digits of symbol
    * 
    * @param price Price.
    * @param symbol Input Symbol. In case of NULL means current symbol.
    * @return Normalized price. If symbol is not available in market watch, return 0
    */
    double NormalizePrice(const double price, const string symbol = NULL)
    {
        CSymbolInfo info;
        if (info.Name(symbol))
        {
            return info.NormalizePrice(price);
        }

        return 0;
    }
    /**
     * @brief Calculate distance points of entry and stop loss.
     * 
     * @param entry Entry point.
     * @param sl Stop loss point.
     * @param symbol Input symbol. In case of NULL means current symbol.
     * @return Distance points. If symbol is not available in market watch, return 0
     */
    long RiskPeriod(const double entry, const double sl, const string symbol = NULL)
    {
        CSymbolInfo info;
        if (info.Name(symbol))
        {
            double point = info.Point();
            double period = MathAbs(entry - sl);
            return period / point;
        }

        return 0;
    }
}