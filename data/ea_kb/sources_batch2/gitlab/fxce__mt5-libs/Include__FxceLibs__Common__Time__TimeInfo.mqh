class CFxceTimeInfo
{
private:
    CFxceTimeInfo(/* args */) {}
    ~CFxceTimeInfo() {}

public:
    /**
     * @brief Return hour of input date time.
     * 
     * @param inpTime Value of datetime type. In case inpTime = NULL, It mean current time
     * @return int Value of Integer type
     */
    static int Hour(const datetime inpTime = NULL)
    {
        ResetLastError();
        MqlDateTime stTime;
        if (inpTime == NULL)
        {
            if (!TimeToStruct(TimeCurrent(), stTime))
            {
                Print("Can't convert to time struct. Error = ", GetLastError());
            }
        }
        else
        {
            if (!TimeToStruct(inpTime, stTime))
            {
                Print("Can't convert to time struct. Error = ", GetLastError());
            }
        }
        return stTime.hour;
    }
    /**
     * @brief Return Minute of input date time
     * 
     * @param inpTime Value of datetime type. In case inpTime = NULL, It mean current time
     * @return int Value of Integer type
     */
    static int Minute(const datetime inpTime = NULL)
    {
        ResetLastError();
        MqlDateTime stTime;
        if (inpTime == NULL)
        {
            if (!TimeToStruct(TimeCurrent(), stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        else
        {
            if (!TimeToStruct(inpTime, stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        return stTime.min;
    }
    /**
     * @brief Return Second of input date time
     * 
     * @param inpSecond Value of datetime type. In case inpTime = NULL, It mean current time
     * @return int Value of Integer type
     */
    static int Second(const datetime inpTime = NULL)
    {
        ResetLastError();
        MqlDateTime stTime;
        if (inpTime == NULL)
        {
            if (!TimeToStruct(TimeCurrent(), stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        else
        {
            if (!TimeToStruct(inpTime, stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        return stTime.sec;
    }
    /**
     * @brief Return Day of input date time
     * 
     * @param inpDay Value of datetime type. In case inpTime = NULL, It mean current time
     * @return int Value of Integer type
     */
    static int Day(const datetime inpTime = NULL)
    {
        ResetLastError();
        MqlDateTime stTime;
        if (inpTime == NULL)
        {
            if (!TimeToStruct(TimeCurrent(), stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        else
        {
            if (!TimeToStruct(inpTime, stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        return stTime.day;
    }
    /**
     * @brief Return Month of input date time
     * 
     * @param inpMonth Value of datetime type. In case inpTime = NULL, It mean current time
     * @return int  Value of Integer type
     */
    static int Month(const datetime inpTime = NULL)
    {
        ResetLastError();
        MqlDateTime stTime;
        if (inpTime == NULL)
        {
            if (!TimeToStruct(TimeCurrent(), stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        else
        {
            if (!TimeToStruct(inpTime, stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        return stTime.mon;
    }
    /**
    * @brief Return Year of input date time
    * 
    * @param inpYear Value of date time type. In case inpTime = NULL, It mean current time
    * @return int Value of Integer type
    */
    static int Year(const datetime inpTime = NULL)
    {
        ResetLastError();
        MqlDateTime stTime;
        if (inpTime == NULL)
        {
            if (!TimeToStruct(TimeCurrent(), stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        else
        {
            if (!TimeToStruct(inpTime, stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        return stTime.year;
    }
    /**
    * @brief Return Dayofweek of input date time
    * 
    * @param inpDayofweek Value of date time type. In case inpTime = NULL, It mean current time
    * @return int Value of Integer type
    */
    static int DayOfWeek(const datetime inpTime = NULL)
    {
        ResetLastError();
        MqlDateTime stTime;
        if (inpTime == NULL)
        {
            if (!TimeToStruct(TimeCurrent(), stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        else
        {
            if (!TimeToStruct(inpTime, stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        return stTime.day_of_week;
    }
    /**
    * @brief Return Dayofyear of input date time
    * 
    * @param inpDayofyear Value of date time type. In case inpTime = NULL, It mean current time
    * @return int Value of Integer type
    */
    static int DayOfYear(const datetime inpTime = NULL)
    {
        ResetLastError();
        MqlDateTime stTime;
        if (inpTime == NULL)
        {
            if (!TimeToStruct(TimeCurrent(), stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        else
        {
            if (!TimeToStruct(inpTime, stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        return stTime.day_of_year;
    }
    /**
    * @brief Return Weekofyear of input date time
    * 
    * @param inpWeekofyear Value of date time type. In case inpTime = NULL, It mean current time
    * @return int Value of Integer type
    */
    static int WeekOfYear(const datetime inpTime = NULL)
    {
        ResetLastError();
        MqlDateTime stTime;
        if (inpTime == NULL)
        {
            if (!TimeToStruct(TimeCurrent(), stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        else
        {
            if (!TimeToStruct(inpTime, stTime))
            {
                Print("Can't covert to time struct. Error = ", GetLastError());
            }
        }
        return (stTime.day_of_year - stTime.day_of_week + 7) / 7;
    }
};