//+------------------------------------------------------------------+
//|                                             CandleSticksInfo.mqh |
//|                                 Copyright 2021, FXCE Company Ltd |
//|                                             https://www.fxce.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2021, FXCE Company Ltd"
#property link "https://www.fxce.com"

namespace FxceCandleSticksInfo
{
    /* ----- Patterns consisting of once candlesticks -----*/

    /**
 * @brief Check Big Candle. The term "Big" refers to a candlestick body length, the difference between the open price and the close price
 * 
 * @param symbol Symbol name
 * @param period Period
 * @param start_pos The start position for the first element to copy
 * @param count Data count to copy
 * @param index_candle Specifies where to perform value calculation
 * @return Return true in case successful, otherwise false. 
 */
    bool BigCandle(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);

        double sum = 0;
        for (int i = 1; i < count; i++)
            sum = sum + MathAbs(candle[i].open - candle[i].close);
        sum = sum / count;

        if (BodySizeCandle(symbol, period, start_pos, count, index_candle) > sum * 1.3)
        {
            return true;
        }
        return false;
    }

    /**
 * @brief Check Small Candle. The term "Small" refers to a candlestick body length, the difference between the open price and the close price
 * 
 * @param symbol Symbol name
 * @param period Period
 * @param start_pos The start position for the first element to copy
 * @param count Data count to copy
 * @param index_candle Specifies where to perform value calculation
 * @return Return true in case successful, otherwise false. 
 */
    bool SmallCandle(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);

        double sum = 0;
        for (int i = 1; i < count; i++)
            sum = sum + MathAbs(candle[i].open - candle[i].close);
        sum = sum / count;

        if (BodySizeCandle(symbol, period, start_pos, count, index_candle) < sum * 0.5)
        {
            return true;
        }
        return false;
    }

    /**
 * @brief Check Bull Candle of input index candle 
 * 
 * @param symbol Symbol name
 * @param period Period
 * @param start_pos The start position for the first element to copy
 * @param count Data count to copy
 * @param index_candle Specifies where to perform value calculation
 * @return Return true in case successful, otherwise false. 
 */
    bool BullCandle(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (candle[index_candle].open < candle[index_candle].close)
        {
            return true;
        }
        return false;
    }

    /**
 * @brief return Value Body Size of input index candle
 * 
 * @param symbol Symbol name
 * @param period Period
 * @param start_pos The start position for the first element to copy
 * @param count Data count to copy
 * @param index_candle Specifies where to perform value calculation
 * @return double Value of Double type
 */
    double BodySizeCandle(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        double body = MathAbs(candle[index_candle].open - candle[index_candle].close);
        if (body < 0)
        {
            Print("Can't search Body Size candle index of count candle. Error = ", GetLastError());
        }
        return body;
    }

    /**
 * @brief return Value Shadows Low of input index candle
 * 
 * @param symbol Symbol name
 * @param period Period
 * @param start_pos The start position for the first element to copy
 * @param count Data count to copy
 * @param index_candle Specifies where to perform value calculation
 * @return double Value of Double type
 */
    double ShadowsLow(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        double subLow;
        if (BullCandle(symbol, period, start_pos, count, index_candle) == true)
        {
            subLow = candle[index_candle].close - candle[index_candle].low;
        }
        if (BullCandle(symbol, period, start_pos, count, index_candle) == false)
        {
            subLow = candle[index_candle].open - candle[index_candle].low;
        }
        return subLow;
    }

    /**
 * @brief return Value Shadows High of input index candle
 * 
 * @param symbol Symbol name
 * @param period Period
 * @param start_pos The start position for the first element to copy
 * @param count Data count to copy
 * @param index_candle Specifies where to perform value calculation
 * @return double Value of Double type
 */
    double ShadowsHigh(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        double subHigh;
        if (BullCandle(symbol, period, start_pos, count, index_candle) == true)
        {
            subHigh = candle[index_candle].high - candle[index_candle].open;
        }
        if (BullCandle(symbol, period, start_pos, count, index_candle) == false)
        {
            subHigh = candle[index_candle].high - candle[index_candle].close;
        }
        return subHigh;
    }

    /**
 * @brief return Value Range Candle of input index candle
 * 
 * @param symbol Symbol name
 * @param period Period
 * @param start_pos The start position for the first element to copy
 * @param count Data count to copy
 * @param index_candle Specifies where to perform value calculation
 * @return double Value of Double type
 */
    double HighLow(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        double highLow = candle[index_candle].high - candle[index_candle].low;
        if (highLow < 0)
        {
            Print("Can't search High Low candle index of count candle. Error = ", GetLastError());
        }
        return highLow;
    }

    /**
  * @brief Check Doji Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool Doji(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        if (BodySizeCandle(symbol, period, start_pos, count, index_candle) < HighLow(symbol, period, start_pos, count, index_candle) * 0.03)
        {
            return true;
        }
        Print("Can't search Doji candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Marubozu Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool Marubozu(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        if ((ShadowsLow(symbol, period, start_pos, count, index_candle) < BodySizeCandle(symbol, period, start_pos, count, index_candle) * 0.01 || ShadowsHigh(symbol, period, start_pos, count, index_candle) < BodySizeCandle(symbol, period, start_pos, count, index_candle) * 0.01) && BodySizeCandle(symbol, period, start_pos, count, index_candle) > 0)
        {
            return true;
        }
        Print("Can't search Marubozu candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Hammer Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool Hammer(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        if (ShadowsLow(symbol, period, start_pos, count, index_candle) > BodySizeCandle(symbol, period, start_pos, count, index_candle) * 2 && ShadowsHigh(symbol, period, start_pos, count, index_candle) < BodySizeCandle(symbol, period, start_pos, count, index_candle) * 0.1)
        {
            return true;
        }
        Print("Can't search Hammer candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Shooting Star Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ShootingStar(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        if (ShadowsLow(symbol, period, start_pos, count, index_candle) < BodySizeCandle(symbol, period, start_pos, count, index_candle) * 0.1 && ShadowsHigh(symbol, period, start_pos, count, index_candle) > BodySizeCandle(symbol, period, start_pos, count, index_candle) * 2)
        {
            return true;
        }
        Print("Can't search Shooting Star candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Spinning Tops Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool SpinningTops(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        if (SmallCandle(symbol, period, start_pos, count, index_candle) && ShadowsLow(symbol, period, start_pos, count, index_candle) > BodySizeCandle(symbol, period, start_pos, count, index_candle) && ShadowsHigh(symbol, period, start_pos, count, index_candle) > BodySizeCandle(symbol, period, start_pos, count, index_candle))
        {
            return true;
        }
        Print("Can't search Spinning Tops candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /* --- Patterns consisting of two candlesticks ---*/

    /**
  * @brief Check Engulfing Bull Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool EngulfingBull(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 1) && BullCandle(symbol, period, start_pos, count, index_candle) && BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) < BodySizeCandle(symbol, period, start_pos, count, index_candle))
        {
            if (candle[index_candle + 1].close >= candle[index_candle].open && candle[index_candle + 1].open < candle[index_candle].close)
                return true;
        }
        Print("Can't search Engulfing Bull candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Engulfing Bear Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool EngulfingBear(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle) && BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) < BodySizeCandle(symbol, period, start_pos, count, index_candle))
        {
            if (candle[index_candle + 1].close <= candle[index_candle].open && candle[index_candle + 1].open > candle[index_candle].close)
                return true;
        }
        Print("Can't search Engulfing Bear candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Harami Cross Bull Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool HaramiCrossBull(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 1) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && Doji(symbol, period, start_pos, count, index_candle))
        {
            if (candle[index_candle + 1].close <= candle[index_candle].open && candle[index_candle + 1].close <= candle[index_candle].close && candle[index_candle + 1].open > candle[index_candle].close)
                return true;
        }
        Print("Can't search Harami Cross Bull candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Harami Cross Bearish Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool HaramiCrossBearish(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 1) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && Doji(symbol, period, start_pos, count, index_candle))
        {
            if (candle[index_candle + 1].close >= candle[index_candle].open && candle[index_candle + 1].close >= candle[index_candle].close && candle[index_candle + 1].open < candle[index_candle].close)
                return true;
        }
        Print("Can't search Harami Cross Bearish candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Harami Bull Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool HaramiBull(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 1) && BullCandle(symbol, period, start_pos, count, index_candle) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && !Doji(symbol, period, start_pos, count, index_candle) && BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) > BodySizeCandle(symbol, period, start_pos, count, index_candle))
        {
            if (candle[index_candle + 1].close <= candle[index_candle].open && candle[index_candle + 1].close <= candle[index_candle].close && candle[index_candle + 1].open > candle[index_candle].close)
                return true;
        }
        Print("Can't search Harami Bull candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Harami Bearish Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool HaramiBearish(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && !Doji(symbol, period, start_pos, count, index_candle) && BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) > BodySizeCandle(symbol, period, start_pos, count, index_candle))
        {
            if (candle[index_candle + 1].close >= candle[index_candle].open && candle[index_candle + 1].close >= candle[index_candle].close && candle[index_candle + 1].open < candle[index_candle].close)
                return true;
        }
        Print("Can't search Harami Bearish candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Doji Star Bull Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool DojiStarBull(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 1) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && Doji(symbol, period, start_pos, count, index_candle))
        {
            if (candle[index_candle + 1].close >= candle[index_candle].open && candle[index_candle + 1].close > candle[index_candle].close)
                return true;
        }
        Print("Can't search Doji Star Bull candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Doji Star Bear Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool DojiStarBear(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 1) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && Doji(symbol, period, start_pos, count, index_candle))
        {
            if (candle[index_candle + 1].close <= candle[index_candle].open && candle[index_candle + 1].close < candle[index_candle].close)
                return true;
        }
        Print("Can't search Doji Star Bear candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Piercing Bull Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool PiercingBull(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 1) && BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)) && candle[index_candle].close > (candle[index_candle + 1].close + candle[index_candle + 1].open) / 2)
            {
                if (candle[index_candle + 1].close >= candle[index_candle].open && candle[index_candle].close <= candle[index_candle + 1].open && candle[index_candle].open < candle[index_candle + 1].low)
                    return true;
            }
        }
        Print("Can't search Piercing Bull candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Dark Cloud Cover Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool DarkCloudCover(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)) && candle[index_candle].close < (candle[index_candle + 1].close + candle[index_candle + 1].open) / 2)
            {
                if (candle[index_candle + 1].close <= candle[index_candle].open && candle[index_candle].close >= candle[index_candle + 1].open && candle[index_candle + 1].high < candle[index_candle].open)
                    return true;
            }
        }
        Print("Can't search Dark Cloud Cover candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Meeting Lines Bull Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool MeetingLinesBull(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 1) && BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)) && candle[index_candle + 1].close == candle[index_candle].close && BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) < BodySizeCandle(symbol, period, start_pos, count, index_candle) && candle[index_candle + 1].low > candle[index_candle].open)
                return true;
        }
        Print("Can't search Meeting Lines Bull candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Meeting Lines Bear Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool MeetingLinesBear(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && candle[index_candle + 1].close == candle[index_candle].close && BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) < BodySizeCandle(symbol, period, start_pos, count, index_candle) && candle[index_candle + 1].high < candle[index_candle].open)
                return true;
        }
        Print("Can't search Meeting Lines Bear candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Matching Low Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool MatchingLow(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if (candle[index_candle + 1].close == candle[index_candle].close && BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) > BodySizeCandle(symbol, period, start_pos, count, index_candle))
                return true;
        }
        Print("Can't search Matching Low candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Homing Pigeon Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool HomingPigeon(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && candle[index_candle + 1].close < candle[index_candle].close && candle[index_candle + 1].open > candle[index_candle].open)
                return true;
        }
        Print("Can't search Homing Pigeon candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /* --- Patterns consisting of three candlesticks ---*/

    /**
  * @brief Check Abandoned Baby Bull Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool AbandonedBabyBull(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 2) && BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)) && Doji(symbol, period, start_pos, count, index_candle + 1) && candle[index_candle].close < candle[index_candle + 2].open && candle[index_candle].close > candle[index_candle + 2].close)
            {
                if (candle[index_candle + 2].low > candle[index_candle + 1].high && candle[index_candle].low > candle[index_candle + 1].high)
                    return true;
            }
        }
        Print("Can't search Abandoned Baby Bull candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Abandoned Baby Bear Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool AbandonedBabyBear(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)) && Doji(symbol, period, start_pos, count, index_candle + 1) && candle[index_candle].close > candle[index_candle + 2].open && candle[index_candle].close < candle[index_candle + 2].close)
            {
                if (candle[index_candle + 2].high < candle[index_candle + 1].low && candle[index_candle].high < candle[index_candle + 1].low)
                    return true;
            }
        }
        Print("Can't search Abandoned Baby Bear candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Morning Star Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool MorningStar(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 2) && BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)) && SmallCandle(symbol, period, start_pos, count, index_candle + 1) && candle[index_candle + 1].close > candle[index_candle + 2].close && candle[index_candle].close < candle[index_candle + 2].open)
            {
                if (candle[index_candle + 1].open <= candle[index_candle + 2].close && candle[index_candle + 1].close < candle[index_candle + 2].close)
                    return true;
            }
        }
        Print("Can't search Morning Star candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Evening Star Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool EveningStar(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)) && SmallCandle(symbol, period, start_pos, count, index_candle + 1) && candle[index_candle].close < candle[index_candle + 2].close && candle[index_candle].close > candle[index_candle + 2].open)
            {
                if (candle[index_candle + 1].open >= candle[index_candle + 2].close && candle[index_candle + 1].close > candle[index_candle + 2].close)
                    return true;
            }
        }
        Print("Can't search Evening Star candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Morning Doji Star Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool MorningDojiStar(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 2) && BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)) && Doji(symbol, period, start_pos, count, index_candle + 1) && candle[index_candle].close > candle[index_candle + 2].close && candle[index_candle].close < candle[index_candle + 2].open)
            {
                if (candle[index_candle + 1].open <= candle[index_candle + 2].close)
                    return true;
            }
        }
        Print("Can't search Morning Doji Star candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Evening Doji Star Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool EveningDojiStar(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)) && Doji(symbol, period, start_pos, count, index_candle + 1) && candle[index_candle].close < candle[index_candle + 2].close && candle[index_candle].close > candle[index_candle + 2].open)
            {
                if (candle[index_candle + 1].open >= candle[index_candle + 2].close)
                    return true;
            }
        }
        Print("Can't search Evening Doji Star candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Upside Gap Two Crows Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool UpsideGapTwoCrows(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && candle[index_candle + 2].close < candle[index_candle + 1].close && candle[index_candle + 2].close < candle[index_candle].close && candle[index_candle + 1].open < candle[index_candle].open && candle[index_candle + 1].close > candle[index_candle].close)
                return true;
        }
        Print("Can't search Upside Gap Two Crows candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Two Crows Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool TwoCrows(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)) && candle[index_candle + 2].close < candle[index_candle + 1].close && candle[index_candle].open > candle[index_candle + 1].close && candle[index_candle].close < candle[index_candle + 2].close)
                return true;
        }
        Print("Can't search Two Crows candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Three Star Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ThreeStar(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (SmallCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)) && BodySizeCandle(symbol, period, start_pos, count, index_candle + 2) > BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) && candle[index_candle + 2].low < candle[index_candle + 1].low && candle[index_candle].low > candle[index_candle + 1].low && candle[index_candle].high < candle[index_candle + 1].high)
                //if (candle[index_candle + 2].close < candle[index_candle + 1].open && candle[index_candle + 1].close < candle[index_candle].open)
                return true;
        }
        Print("Can't search Three Star candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Deliberation Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool Deliberation(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 2) && BullCandle(symbol, period, start_pos, count, index_candle + 1) && BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && SpinningTops(symbol, period, start_pos, count, index_candle) || SmallCandle(symbol, period, start_pos, count, index_candle))
                // if (candle[index_candle + 2].close > candle[index_candle + 1].open && candle[index_candle + 1].close <= candle[index_candle].open)
                return true;
        }
        Print("Can't search Deliberation candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Three White Soldiers Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ThreeWhiteSoldiers(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 2) && BullCandle(symbol, period, start_pos, count, index_candle + 1) && BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)))
                //  if (candle[index_candle + 2].close > candle[index_candle + 1].open && candle[index_candle + 1].close > candle[index_candle].open)
                return true;
        }
        Print("Can't search Three White Soldiers candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Three Black Crows Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ThreeBlackCrows(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)))
                return true;
        }
        Print("Can't search Three Black Crows candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Three Outside Up Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ThreeOutsideUp(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 2) && BullCandle(symbol, period, start_pos, count, index_candle + 1) && BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if (BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) > BodySizeCandle(symbol, period, start_pos, count, index_candle + 2) && candle[index_candle].close > candle[index_candle + 1].close)
                if (candle[index_candle + 2].close >= candle[index_candle + 1].open && candle[index_candle + 2].open < candle[index_candle + 1].close)
                    return true;
        }
        Print("Can't search Three Outside Up candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Three Outside Down Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ThreeOutsideDown(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if (BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) > BodySizeCandle(symbol, period, start_pos, count, index_candle + 2) && candle[index_candle].close < candle[index_candle + 1].close)
                if (candle[index_candle + 2].close <= candle[index_candle + 1].open && candle[index_candle + 2].open > candle[index_candle + 1].close)
                    return true;
        }
        Print("Can't search Three Outside Down candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Three Inside Up Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ThreeInsideUp(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 2) && BullCandle(symbol, period, start_pos, count, index_candle + 1) && BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && BodySizeCandle(symbol, period, start_pos, count, index_candle + 2) > BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) && candle[index_candle].close > candle[index_candle + 1].close)
                if (candle[index_candle + 2].close <= candle[index_candle + 1].open && candle[index_candle + 2].close <= candle[index_candle + 1].close && candle[index_candle + 2].open > candle[index_candle + 1].close)
                    return true;
        }
        Print("Can't search Three Inside Up candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Three Inside Down Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ThreeInsideDown(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && BodySizeCandle(symbol, period, start_pos, count, index_candle + 2) > BodySizeCandle(symbol, period, start_pos, count, index_candle + 1) && candle[index_candle].close < candle[index_candle + 1].close)
                if (candle[index_candle + 2].close >= candle[index_candle + 1].open && candle[index_candle + 2].close >= candle[index_candle + 1].close && candle[index_candle + 2].close >= candle[index_candle + 1].close)
                    return true;
        }
        Print("Can't search Three Inside Down candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Three Stars Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ThreeStars(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (Doji(symbol, period, start_pos, count, index_candle + 2) && Doji(symbol, period, start_pos, count, index_candle + 1) && Doji(symbol, period, start_pos, count, index_candle))
        {
            //if (candle[index_candle + 1].open != candle[index_candle + 2].close && candle[index_candle + 1].close != candle[index_candle].open)
            return true;
        }
        Print("Can't search Three Stars candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Identical Three Crows Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool IdenticalThreeCrows(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle))
        {
            if ((BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)))
                // if (candle[index_candle + 2].close >= candle[index_candle + 1].open && candle[index_candle + 1].close >= candle[index_candle].open)
                return true;
        }
        Print("Can't search Identical Three Crows candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Unique Three River Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool UniqueThreeRiver(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle + 1) && BullCandle(symbol, period, start_pos, count, index_candle) && (BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && SmallCandle(symbol, period, start_pos, count, index_candle))
        {
            if (candle[index_candle + 1].open < candle[index_candle + 2].open && candle[index_candle + 1].close > candle[index_candle + 2].close && candle[index_candle + 1].low < candle[index_candle + 2].low && candle[index_candle].close < candle[index_candle + 1].close)
                return true;
        }
        Print("Can't search Unique Three River candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /* ----- Patterns consisting of four candlesticks -----*/

    /**
  * @brief Check Concealing Baby Swallow Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ConcealingBabySwallow(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 3) && !BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle) && Marubozu(symbol, period, start_pos, count, index_candle + 3) && Marubozu(symbol, period, start_pos, count, index_candle + 2) && SmallCandle(symbol, period, start_pos, count, index_candle + 1))
        {
            if (candle[index_candle + 1].open < candle[index_candle + 2].close && candle[index_candle + 1].high > candle[index_candle + 2].close && candle[index_candle].open > candle[index_candle + 1].high && candle[index_candle].close < candle[index_candle + 1].low)
                return true;
        }
        Print("Can't search Concealing Baby Swallow candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Three-Line Strike Bull Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ThreeLineStrikeBull(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 3) && BullCandle(symbol, period, start_pos, count, index_candle + 2) && BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle) && (BigCandle(symbol, period, start_pos, count, index_candle + 3) || Marubozu(symbol, period, start_pos, count, index_candle + 3)) && (BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)))
        {
            if (candle[index_candle + 2].close > candle[index_candle + 3].close && candle[index_candle + 1].close > candle[index_candle + 2].close && candle[index_candle].close < candle[index_candle + 3].open)
            {
                if (candle[index_candle].open >= candle[index_candle + 1].close)
                    return true;
            }
        }
        Print("Can't search Three-Line Strike Bull candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /**
  * @brief Check Three-Line Strike Bear Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool ThreeLineStrikeBear(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 3) && !BullCandle(symbol, period, start_pos, count, index_candle + 2) && !BullCandle(symbol, period, start_pos, count, index_candle + 1) && BullCandle(symbol, period, start_pos, count, index_candle) && (BigCandle(symbol, period, start_pos, count, index_candle + 3) || Marubozu(symbol, period, start_pos, count, index_candle + 3)) && (BigCandle(symbol, period, start_pos, count, index_candle + 2) || Marubozu(symbol, period, start_pos, count, index_candle + 2)) && (BigCandle(symbol, period, start_pos, count, index_candle + 1) || Marubozu(symbol, period, start_pos, count, index_candle + 1)))
        {
            if (candle[index_candle + 2].close < candle[index_candle + 3].close && candle[index_candle + 1].close < candle[index_candle + 2].close && candle[index_candle].close > candle[index_candle + 3].open)
            {
                if (candle[index_candle].open <= candle[index_candle + 1].close)
                    return true;
            }
        }
        Print("Can't search Three-Line Strike Bear candle index of count candle. Error = ", GetLastError());
        return false;
    }

    /* ----- Patterns consisting of five candlesticks -----*/

    /**
  * @brief Check Breakaway Bull Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool BreakawayBull(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (!BullCandle(symbol, period, start_pos, count, index_candle + 4) && !BullCandle(symbol, period, start_pos, count, index_candle + 3) && !BullCandle(symbol, period, start_pos, count, index_candle + 1) && BullCandle(symbol, period, start_pos, count, index_candle) && (BigCandle(symbol, period, start_pos, count, index_candle + 4) || Marubozu(symbol, period, start_pos, count, index_candle + 4)) && SmallCandle(symbol, period, start_pos, count, index_candle + 3) && candle[index_candle + 3].open < candle[index_candle + 4].close)
        {
            if (SmallCandle(symbol, period, start_pos, count, index_candle + 2) && SmallCandle(symbol, period, start_pos, count, index_candle + 1) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)))
            {
                if (candle[index_candle].close < candle[index_candle + 4].close && candle[index_candle].close > candle[index_candle + 3].open)
                    return true;
            }
        }
        Print("Can't search Breakaway Bull candle index of count candle. Error = ", GetLastError());
        return false;
    }
    /**
  * @brief Check Breakaway Bear Candle of input index candle 
  * 
  * @param symbol Symbol name
  * @param period Period
  * @param start_pos The start position for the first element to copy
  * @param count Data count to copy
  * @param index_candle Specifies where to perform value calculation 
  * @return Return true in case successful, otherwise false. 
  */
    bool BreakawayBear(const string symbol, const ENUM_TIMEFRAMES period, const int start_pos, const int count, const int index_candle)
    {
        ResetLastError();
        MqlRates candle[];
        CopyRates(symbol, period, start_pos, count, candle);
        if (BullCandle(symbol, period, start_pos, count, index_candle + 4) && BullCandle(symbol, period, start_pos, count, index_candle + 3) && BullCandle(symbol, period, start_pos, count, index_candle + 1) && !BullCandle(symbol, period, start_pos, count, index_candle) && (BigCandle(symbol, period, start_pos, count, index_candle + 4) || Marubozu(symbol, period, start_pos, count, index_candle + 4)) && SmallCandle(symbol, period, start_pos, count, index_candle + 3) && candle[index_candle + 3].open < candle[index_candle + 4].close)
        {
            if (SmallCandle(symbol, period, start_pos, count, index_candle + 2) && SmallCandle(symbol, period, start_pos, count, index_candle + 1) && (BigCandle(symbol, period, start_pos, count, index_candle) || Marubozu(symbol, period, start_pos, count, index_candle)))
            {
                if (candle[index_candle].close > candle[index_candle + 4].close && candle[index_candle].close < candle[index_candle + 3].open)
                    return true;
            }
        }
        Print("Can't search Breakaway Bear candle index of count candle. Error = ", GetLastError());
        return false;
    }
}
