namespace CFxcePriceInfo
{

    /**
     * @brief Return Hight price of the input date time
    * 
    * @param symbol Input Symbol. In case of NULL means current symbol.
    * @param timeframe Input Time frame Period. It can be one of the values of the ENUM_TIMEFRAMES enumeration. 
    *                  In case of PERIOD_CURRENT means the current chart period.
    * @param time Input Time value to search for. In case of time TimeCurrent() means the current chart period.
    * @param exact A return value, in case the bar with the specified time is not found.
    *                  If exact=false, iBarShift returns the index of the nearest bar, the Open time of which is less than the specified time (time_open<time).
    *                   If such a bar is not found (history before the specified time is not available), then the function returns -1. If exact=true, iBarShift does not search for a nearest bar but immediately returns -1.
    * @return double Value of Double type
    */
    double HightPriceOfTime(const string symbol, const ENUM_TIMEFRAMES timeframe, const datetime time, const bool exact = false)
    {
        int timeBarHigh = iBarShift(symbol, timeframe, time, exact);
        double highPriceOfTime = iHigh(symbol, timeframe, timeBarHigh);
        ResetLastError();
        if (time == NULL)
        {
            Print("Can't search high price of time value. Error = ", GetLastError());
        }
        else if (timeframe == NULL)
        {
            Print("Can't search high price of time frame. Error = ", GetLastError());
        }
        return highPriceOfTime;
    }
    /**
     * @brief Return Low price of the input date time
    * 
    * @param symbol Input Symbol. In case of NULL means current symbol.
    * @param timeframe Input Time frame Period. It can be one of the values of the ENUM_TIMEFRAMES enumeration. 
    *                  In case of PERIOD_CURRENT means the current chart period.
    * @param time Input Time value to search for. In case of time TimeCurrent() means the current chart period.
    * @param exact A return value, in case the bar with the specified time is not found.
    *                  If exact=false, iBarShift returns the index of the nearest bar, the Open time of which is less than the specified time (time_open<time).
    *                  If such a bar is not found (history before the specified time is not available), then the function returns -1. If exact=true, iBarShift does not search for a nearest bar but immediately returns -1.
    * @return double Value of Double type
    */
    double LowPriceOfTime(const string symbol, const ENUM_TIMEFRAMES timeframe, const datetime time, const bool exact = false)
    {
        int timeBarLow = iBarShift(symbol, timeframe, time, exact);
        double lowPriceOfTime = iLow(symbol, timeframe, timeBarLow);
        ResetLastError();
        if (time == NULL)
        {
            Print("Can't search high price of time value. Error = ", GetLastError());
        }
        else if (timeframe == NULL)
        {
            Print("Can't search high price of time frame. Error = ", GetLastError());
        }
        return lowPriceOfTime;
    }
    /**
     * @brief Return Open price of the input date time
    * 
    * @param symbol Input Symbol. In case of NULL means current symbol.
    * @param timeframe Input Time frame Period. It can be one of the values of the ENUM_TIMEFRAMES enumeration. 
    *                  In case of PERIOD_CURRENT means the current chart period.
    * @param time Input Time value to search for. In case of time TimeCurrent() means the current chart period.
    * @param exact A return value, in case the bar with the specified time is not found.
    *                  If exact=false, iBarShift returns the index of the nearest bar, the Open time of which is less than the specified time (time_open<time).
    *                  If such a bar is not found (history before the specified time is not available), then the function returns -1. If exact=true, iBarShift does not search for a nearest bar but immediately returns -1.
    * @return double Value of Double type
    */
    double OpenPriceOfTime(const string symbol, const ENUM_TIMEFRAMES timeframe, const datetime time, const bool exact = false)
    {
        int timeBarOpen = iBarShift(symbol, timeframe, time, exact);
        double openPriceOfTime = iOpen(symbol, timeframe, timeBarOpen);
        ResetLastError();
        if (time == NULL)
        {
            Print("Can't search high price of time value. Error = ", GetLastError());
        }
        else if (timeframe == NULL)
        {
            Print("Can't search high price of time frame. Error = ", GetLastError());
        }
        return openPriceOfTime;
    }

    /**
     * @brief Return Close price of the input date time
    * 
    * @param symbol Input Symbol. In case of NULL means current symbol.
    * @param timeframe Input Time frame Period. It can be one of the values of the ENUM_TIMEFRAMES enumeration. 
    *                  In case of PERIOD_CURRENT means the current chart period.
    * @param time Input Time value to search for. In case of time TimeCurrent() means the current chart period.
    * @param exact A return value, in case the bar with the specified time is not found.
    *                  If exact=false, iBarShift returns the index of the nearest bar, the Open time of which is less than the specified time (time_open<time).
    *                  If such a bar is not found (history before the specified time is not available), then the function returns -1. If exact=true, iBarShift does not search for a nearest bar but immediately returns -1.
    * @return double Value of Double type
    */
    double ClosePriceOfTime(const string symbol, const ENUM_TIMEFRAMES timeframe, const datetime time, const bool exact = false)
    {
        int timeBarClose = iBarShift(symbol, timeframe, time, exact);
        double closePriceOfTime = iClose(symbol, timeframe, timeBarClose);
        ResetLastError();
        if (time == NULL)
        {
            Print("Can't search high price of time value. Error = ", GetLastError());
        }
        else if (timeframe == NULL)
        {
            Print("Can't search high price of time frame. Error = ", GetLastError());
        }
        return closePriceOfTime;
    }
};
