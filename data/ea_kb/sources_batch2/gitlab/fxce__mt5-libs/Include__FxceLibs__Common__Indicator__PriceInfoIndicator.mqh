namespace CFxcePriceInfoIndicator
{
    /**
     * @brief return Value of input index Moving Average
     * 
     * @param symbol The symbol name of the security, the data of which should be used to calculate the indicator. The NULL value means the current symbol
     * @param period The value of the period can be one of the ENUM_TIMEFRAMES values, 0 means the current timeframe.
     * @param ma_period Averaging period for the calculation of the moving average.
     * @param ma_shift  Shift of the indicator relative to the price chart.
     * @param ma_method Smoothing type. Can be one of the ENUM_MA_METHOD values.
     * @param applied_price The price used. Can be any of the price constants ENUM_APPLIED_PRICE or a handle of another indicator.
     * @param index_ma_convert Specifies where to perform value conversion.
     * @return double Value of Double type
     */
    double ConvertMA(const string symbol, const ENUM_TIMEFRAMES period, const int ma_period, const int ma_shift, const ENUM_MA_METHOD ma_method, const ENUM_APPLIED_PRICE applied_price, const int index_ma_convert)
    {
        int maLocation = iMA(symbol, period, ma_period, ma_shift, ma_method, applied_price);
        double maValue[];
        CopyBuffer(maLocation, 0, 0, ma_period, maValue);
        ArrayReverse(maValue);
        ResetLastError();
        if (ma_period == NULL)
        {
            Print("Can't search Averaging period of Moving Average. Error = ", GetLastError());
        }
        else if (index_ma_convert == NULL)
        {
            Print("Can't search value conversion of Moving Average. Error = ", GetLastError());
        }
        return maValue[index_ma_convert];
    }
    /**
     * @brief return Value of input index RSI
     * 
     * @param symbol  The symbol name of the security, the data of which should be used to calculate the indicator. The NULL value means the current symbol.
     * @param period The value of the period can be one of the ENUM_TIMEFRAMES values, 0 means the current timeframe.
     * @param ma_period Averaging period for the RSI calculation.
     * @param applied_price The price used. Can be any of the price constants ENUM_APPLIED_PRICE or a handle of another indicator.
     * @param index_rsi_convert Specifies where to perform value conversion.
     * @return double Value of Double type.
     */
    double ConvertRSI(const string symbol, const ENUM_TIMEFRAMES period, const int ma_period, const ENUM_APPLIED_PRICE applied_price, const int index_rsi_convert)
    {
        int rsiLocation = iRSI(symbol, period, ma_period, applied_price);
        double rsiValue[];
        CopyBuffer(rsiLocation, 0, 0, ma_period, rsiValue);
        ArrayReverse(rsiValue);
        ResetLastError();
        if (ma_period == NULL)
        {
            Print("Can't search Averaging period of RSI. Error = ", GetLastError());
        }
        else if (index_rsi_convert == NULL)
        {
            Print("Can't search value conversion of RSI. Error = ", GetLastError());
        }
        return rsiValue[index_rsi_convert];
    }
    /**
     * @brief return Value of input index MACD
     * 
     * @param symbol The symbol name of the security, the data of which should be used to calculate the indicator. The NULL value means the current symbol.
     * @param period  The value of the period can be one of the ENUM_TIMEFRAMES values, 0 means the current timeframe.
     * @param fast_ema_period  Period for Fast Moving Average calculation.
     * @param slow_ema_period  Period for Slow Moving Average calculation.
     * @param signal_period Period for Signal line calculation.
     * @param applied_price The price used. Can be any of the price constants ENUM_APPLIED_PRICE or a handle of another indicator.
     * @param index_macd_convert Specifies where to perform value conversion.
     * @return double Value of Double type.
     */
    double ConvertMACD(const string symbol, const ENUM_TIMEFRAMES period, const int fast_ema_period, const int slow_ema_period, const int signal_period, const ENUM_APPLIED_PRICE applied_price, const int index_macd_convert)
    {
        int macdLocation = iMACD(symbol, period, fast_ema_period, slow_ema_period, signal_period, applied_price);
        double macdValue[];
        CopyBuffer(macdLocation, 0, 0, signal_period, macdValue);
        ArrayReverse(macdValue);
        ResetLastError();
        if (signal_period == NULL)
        {
            Print("Can't search Period for Signal line calculation of MACD. Error = ", GetLastError());
        }
        else if (index_macd_convert == NULL)
        {
            Print("Can't search value conversion of MACD. Error = ", GetLastError());
        }
        return macdValue[index_macd_convert];
    }
    /**
     * @brief return Value of input index Stochastic RSI
     * 
     * @param symbol  The symbol name of the security, the data of which should be used to calculate the indicator. The NULL value means the current symbol.
     * @param period The value of the period can be one of the ENUM_TIMEFRAMES values, 0 means the current timeframe.
     * @param Kperiod Averaging period (bars count) for the %K line calculation.
     * @param Dperiod Averaging period (bars count) for the %D line calculation.
     * @param slowing  Slowing value.
     * @param ma_method Type of averaging. Can be any of the ENUM_MA_METHOD values.
     * @param price_field  Parameter of price selection for calculations. Can be one of the ENUM_STO_PRICE values.
     * @param index_StochRSI_convert Specifies where to perform value conversion.
     * @return double Value of Double type.
     */
    double ConvertStochRSI(const string symbol, const ENUM_TIMEFRAMES period, const int Kperiod, const int Dperiod, const int slowing, const ENUM_MA_METHOD ma_method, const ENUM_STO_PRICE price_field, const int index_StochRSI_convert)
    {
        int StockRSILocation = iStochastic(symbol, period, Kperiod, Dperiod, slowing, ma_method, price_field);
        double StochRSIValue[];
        CopyBuffer(StockRSILocation, 0, 0, slowing, StochRSIValue);
        ArrayReverse(StochRSIValue);
        ResetLastError();
        if (slowing == NULL)
        {
            Print("Can't search slowing value of Stochastic RSI. Error = ", GetLastError());
        }
        else if (index_StochRSI_convert == NULL)
        {
            Print("Can't search value conversion of Stochastic RSI. Error = ", GetLastError());
        }
        return StochRSIValue[index_StochRSI_convert];
    }
    /**
     * @brief return Value of input index upper Bollinger Bands
     * 
     * @param symbol The symbol name of the security, the data of which should be used to calculate the indicator. The NULL value means the current symbol.
     * @param period  The value of the period can be one of the ENUM_TIMEFRAMES values, 0 means the current timeframe.
     * @param bands_period  The averaging period of the main line of the indicator.
     * @param bands_shift The shift the indicator relative to the price chart.
     * @param deviation Deviation from the main line.
     * @param applied_price  The price used. Can be any of the price constants ENUM_APPLIED_PRICE or a handle of another indicator.
     * @param index_BB_convert Specifies where to perform value conversion.
     * @return double Value of Double type.
     */
    double ConvertBBUpper(const string symbol, const ENUM_TIMEFRAMES period, const int bands_period, const int bands_shift, const double deviation, const ENUM_APPLIED_PRICE applied_price, const int index_BBUpper_convert)
    {
        int BBUpperLocation = iBands(symbol, period, bands_period, bands_shift, deviation, applied_price);
        double BBUpperValue[];
        CopyBuffer(BBUpperLocation, 1, 0, deviation, BBUpperValue);
        ArrayReverse(BBUpperValue);
        ResetLastError();
        if (deviation == NULL)
        {
            Print("Can't search Deviation from the main line of Bollinger Bands. Error = ", GetLastError());
        }
        else if (index_BBUpper_convert == NULL)
        {
            Print("Can't search upper value conversion of Bollinger Bands. Error = ", GetLastError());
        }
        return BBUpperValue[index_BBUpper_convert];
    }
    /**
     * @brief return Value of input index lower Bollinger Bands
     * 
     * @param symbol The symbol name of the security, the data of which should be used to calculate the indicator. The NULL value means the current symbol.
     * @param period The value of the period can be one of the ENUM_TIMEFRAMES values, 0 means the current timeframe.
     * @param bands_period   The averaging period of the main line of the indicator.
     * @param bands_shift  The shift the indicator relative to the price chart.
     * @param deviation Deviation from the main line.
     * @param applied_price The price used. Can be any of the price constants ENUM_APPLIED_PRICE or a handle of another indicator.
     * @param index_BBLower_convert Specifies where to perform value conversion.
     * @return double Value of Double type.
     */
    double ConvertBBLower(const string symbol, const ENUM_TIMEFRAMES period, const int bands_period, const int bands_shift, const double deviation, const ENUM_APPLIED_PRICE applied_price, const int index_BBLower_convert)
    {
        int BBLowerLocation = iBands(symbol, period, bands_period, bands_shift, deviation, applied_price);
        double BBLowerValue[];
        CopyBuffer(BBLowerLocation, 2, 0, deviation, BBLowerValue);
        ArrayReverse(BBLowerValue);
        ResetLastError();
        if (deviation == NULL)
        {
            Print("Can't search Deviation from the main line of Bollinger Bands. Error = ", GetLastError());
        }
        else if (index_BBLower_convert == NULL)
        {
            Print("Can't search lower value conversion of Bollinger Bands. Error = ", GetLastError());
        }
        return BBLowerValue[index_BBLower_convert];
    }
}
