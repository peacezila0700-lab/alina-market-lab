
namespace FxceTelegram
{
#define CUSTOM_ERROR_FIRST ERR_USER_ERROR_FIRST
#define ERR_JSON_PARSING ERR_USER_ERROR_FIRST + 1
#define ERR_JSON_NOT_OK ERR_USER_ERROR_FIRST + 2
#define ERR_TOKEN_ISEMPTY ERR_USER_ERROR_FIRST + 3
#define ERR_RUN_LIMITATION ERR_USER_ERROR_FIRST + 4
//---
#define ERR_NOT_ACTIVE ERR_USER_ERROR_FIRST + 100
#define ERR_NOT_CONNECTED ERR_USER_ERROR_FIRST + 101
#define ERR_ORDER_SELECT ERR_USER_ERROR_FIRST + 102
#define ERR_INVALID_ORDER_TYPE ERR_USER_ERROR_FIRST + 103
#define ERR_INVALID_SYMBOL_NAME ERR_USER_ERROR_FIRST + 104
#define ERR_INVALID_EXPIRATION_TIME ERR_USER_ERROR_FIRST + 105
#define ERR_HTTP_ERROR_FIRST ERR_USER_ERROR_FIRST + 1000 //+511

#define TELEGRAM_BASE_URL "https://api.telegram.org"
#define WEB_TIMEOUT 5000
    /**
     * @brief ENUM_UPDATE_MODE
     * 
     */
    enum ENUM_UPDATE_MODE
    {
        UPDATE_FAST,   //Fast
        UPDATE_NORMAL, //Normal
        UPDATE_SLOW,   //Slow
    };
    /**
     * @brief ENUM_RUN_MODE
     * 
     */
    enum ENUM_RUN_MODE
    {
        RUN_OPTIMIZATION,
        RUN_VISUAL,
        RUN_TESTER,
        RUN_LIVE
    };
    /**
     * @brief ENUM_ERROR_LEVEL
     * 
     */
    enum ENUM_ERROR_LEVEL
    {
        LEVEL_INFO,
        LEVEL_WARNING,
        LEVEL_ERROR,
        LEVEL_CRITICAL
    };
    /**
     * @brief ENUM_CHAT_ACTION
     * 
     */
    enum ENUM_CHAT_ACTION
    {
        ACTION_FIND_LOCATION,   //picking location...
        ACTION_RECORD_AUDIO,    //recording audio...
        ACTION_RECORD_VIDEO,    //recording video...
        ACTION_TYPING,          //typing...
        ACTION_UPLOAD_AUDIO,    //sending audio...
        ACTION_UPLOAD_DOCUMENT, //sending file...
        ACTION_UPLOAD_PHOTO,    //sending photo...
        ACTION_UPLOAD_VIDEO     //sending video...
    };
    /**
     * @brief CustomInfo
     * 
     */
    struct CustomInfo
    {
        string text1;
        string text2;
        color colour;
        ENUM_ERROR_LEVEL level;
    };
    /**
     * @brief ErrorInfo
     * 
     */
    struct ErrorInfo
    {
        int code;
        string desc;
        ENUM_ERROR_LEVEL level;
    };
    /**
     * @brief Get the Run Mode.
     * 
     * @return ENUM_RUN_MODE 
     */
    ENUM_RUN_MODE GetRunMode(void)
    {
        if (MQLInfoInteger(MQL_OPTIMIZATION))
        {
            return (RUN_OPTIMIZATION);
        }

        if (MQLInfoInteger(MQL_VISUAL_MODE))
        {
            return (RUN_VISUAL);
        }

        if (MQLInfoInteger(MQL_TESTER))
        {
            return (RUN_TESTER);
        }

        return (RUN_LIVE);
    }
    /**
     * @brief Get the error info description.
     * 
     * @param info Output object of ErrorInfo structure.
     * @return Return true in case successful, otherwise false.
     */
    bool GetErrorInfo(ErrorInfo &info)
    {
        info.level = LEVEL_INFO;

        switch (info.code)
        {
        case ERR_NOT_CONNECTED:
            info.desc = "No connection with server";
            info.level = LEVEL_ERROR;
            break;
        case ERR_JSON_PARSING:
            info.desc = "JSON parsing error";
            info.level = LEVEL_ERROR;
            break;
        case ERR_JSON_NOT_OK:
            info.desc = "JSON parsing not OK";
            info.level = LEVEL_ERROR;
            break;
        case ERR_TOKEN_ISEMPTY:
            info.desc = "Token is empty";
            info.level = LEVEL_ERROR;
            break;
        case ERR_RUN_LIMITATION:
            info.desc = "The bot does not run in tester mode";
            info.level = LEVEL_ERROR;
            break;

        case ERR_WEBREQUEST_INVALID_ADDRESS:
            info.desc = "Invalid URL";
            break;
        case ERR_WEBREQUEST_CONNECT_FAILED:
            info.desc = "Failed to connect to specified URL";
            break;
        case ERR_WEBREQUEST_TIMEOUT:
            info.desc = "Timeout exceeded";
            break;
        case ERR_WEBREQUEST_REQUEST_FAILED:
            info.desc = "HTTP request failed";
            break;

#ifdef __MQL4__
        case ERR_FUNCTION_NOT_CONFIRMED:
            info.desc = "URL does not allowed for WebRequest";
            break;
#endif

#ifdef __MQL5__
        case ERR_FUNCTION_NOT_ALLOWED:
            info.desc = "URL does not allowed for WebRequest";
            break;
        case ERR_FILE_NOT_EXIST:
            info.desc = "File is not exists";
            break;
        case ERR_CHART_NOT_FOUND:
            info.desc = "Chart not found";
            break;
        case ERR_SUCCESS:
            info.desc = "The operation completed successfully";
            break;
#endif
        //---
        case ERR_HTTP_ERROR_FIRST + 100:
            info.desc = "Continue";
            break;
        case ERR_HTTP_ERROR_FIRST + 101:
            info.desc = "Switching Protocols";
            break;
        case ERR_HTTP_ERROR_FIRST + 103:
            info.desc = "Checkpoint";
            break;
        case ERR_HTTP_ERROR_FIRST + 200:
            info.desc = "OK";
            break;
        case ERR_HTTP_ERROR_FIRST + 201:
            info.desc = "Created";
            break;
        case ERR_HTTP_ERROR_FIRST + 202:
            info.desc = "Accepted";
            break;
        case ERR_HTTP_ERROR_FIRST + 203:
            info.desc = "Non-Authoritative Information";
            break;
        case ERR_HTTP_ERROR_FIRST + 204:
            info.desc = "No Content";
            break;
        case ERR_HTTP_ERROR_FIRST + 205:
            info.desc = "Reset Content";
            break;
        case ERR_HTTP_ERROR_FIRST + 206:
            info.desc = "Partial Content";
            break;
        case ERR_HTTP_ERROR_FIRST + 300:
            info.desc = "Multiple Choices";
            break;
        case ERR_HTTP_ERROR_FIRST + 301:
            info.desc = "Moved Permanently";
            break;
        case ERR_HTTP_ERROR_FIRST + 302:
            info.desc = "Found";
            break;
        case ERR_HTTP_ERROR_FIRST + 303:
            info.desc = "See Other";
            break;
        case ERR_HTTP_ERROR_FIRST + 304:
            info.desc = "Not Modified";
            break;
        case ERR_HTTP_ERROR_FIRST + 306:
            info.desc = "Switch Proxy";
            break;
        case ERR_HTTP_ERROR_FIRST + 307:
            info.desc = "Temporary Redirect";
            break;
        case ERR_HTTP_ERROR_FIRST + 308:
            info.desc = "Resume Incomplete";
            break;
        case ERR_HTTP_ERROR_FIRST + 400:
            info.desc = "Bad Request";
            break;
        case ERR_HTTP_ERROR_FIRST + 401:
            info.desc = "Unauthorized";
            break;
        case ERR_HTTP_ERROR_FIRST + 402:
            info.desc = "Payment Required";
            break;
        case ERR_HTTP_ERROR_FIRST + 403:
            info.desc = "Forbidden";
            break;
        case ERR_HTTP_ERROR_FIRST + 404:
            info.desc = "Not Found";
            break;
        case ERR_HTTP_ERROR_FIRST + 405:
            info.desc = "Method Not Allowed";
            break;
        case ERR_HTTP_ERROR_FIRST + 406:
            info.desc = "Not Acceptable";
            break;
        case ERR_HTTP_ERROR_FIRST + 407:
            info.desc = "Proxy Authentication Required";
            break;
        case ERR_HTTP_ERROR_FIRST + 408:
            info.desc = "Request Timeout";
            break;
        case ERR_HTTP_ERROR_FIRST + 409:
            info.desc = "Conflict";
            break;
        case ERR_HTTP_ERROR_FIRST + 410:
            info.desc = "Gone";
            break;
        case ERR_HTTP_ERROR_FIRST + 411:
            info.desc = "Length Required";
            break;
        case ERR_HTTP_ERROR_FIRST + 412:
            info.desc = "Precondition Failed";
            break;
        case ERR_HTTP_ERROR_FIRST + 413:
            info.desc = "Request Entity Too Large";
            break;
        case ERR_HTTP_ERROR_FIRST + 414:
            info.desc = "Request-URI Too Long";
            break;
        case ERR_HTTP_ERROR_FIRST + 415:
            info.desc = "Unsupported Media Type";
            break;
        case ERR_HTTP_ERROR_FIRST + 416:
            info.desc = "Requested Range Not Satisfiable";
            break;
        case ERR_HTTP_ERROR_FIRST + 417:
            info.desc = "Expectation Failed";
            break;
        case ERR_HTTP_ERROR_FIRST + 500:
            info.desc = "Internal Server Error";
            break;
        case ERR_HTTP_ERROR_FIRST + 501:
            info.desc = "Not Implemented";
            break;
        case ERR_HTTP_ERROR_FIRST + 502:
            info.desc = "Bad Gateway";
            break;
        case ERR_HTTP_ERROR_FIRST + 503:
            info.desc = "Service Unavailable";
            break;
        case ERR_HTTP_ERROR_FIRST + 504:
            info.desc = "Gateway Timeout";
            break;
        case ERR_HTTP_ERROR_FIRST + 505:
            info.desc = "HTTP Version Not Supported";
            break;
        case ERR_HTTP_ERROR_FIRST + 511:
            info.desc = "Network Authentication Required";
            break;

            //--- The error codes returned by trade server:
#ifdef __MQL4__
        case ERR_NO_ERROR:
            info.desc = "No error";
            break;
        case ERR_NO_RESULT:
            info.desc = "No error returned, but the result is unknown";
            info.level = LEVEL_WARNING;
            break;
        case ERR_COMMON_ERROR:
            info.desc = "Common error.";
            info.level = LEVEL_WARNING;
            break;
        case ERR_INVALID_TRADE_PARAMETERS:
            info.desc = "Invalid trade parameters";
            info.level = LEVEL_WARNING;
            break;
        case ERR_SERVER_BUSY:
            info.desc = "Trade server is busy";
            info.level = LEVEL_WARNING;
            break;
        case ERR_OLD_VERSION:
            info.desc = "Old version of the client terminal";
            info.level = LEVEL_WARNING;
            break;
        case ERR_NO_CONNECTION:
            info.desc = "No connection with trade server";
            info.level = LEVEL_WARNING;
            break;
        case ERR_NOT_ENOUGH_RIGHTS:
            info.desc = "Not enough rights";
            info.level = LEVEL_WARNING;
            break;
        case ERR_TOO_FREQUENT_REQUESTS:
            info.desc = "Too frequent requests";
            info.level = LEVEL_WARNING;
            break;
        case ERR_MALFUNCTIONAL_TRADE:
            info.desc = "Malfunctional trade operation";
            info.level = LEVEL_WARNING;
            break;
        case ERR_ACCOUNT_DISABLED:
            info.desc = "Account disabled";
            info.level = LEVEL_ERROR;
            break;
        case ERR_INVALID_ACCOUNT:
            info.desc = "Invalid account";
            info.level = LEVEL_WARNING;
            break;
        case ERR_TRADE_TIMEOUT:
            info.desc = "Trade timeout";
            info.level = LEVEL_WARNING;
            break;
        case ERR_INVALID_PRICE:
            info.desc = "Invalid price";
            info.level = LEVEL_WARNING;
            break;
        case ERR_INVALID_STOPS:
            info.desc = "Invalid stops";
            info.level = LEVEL_WARNING;
            break;
        case ERR_INVALID_TRADE_VOLUME:
            info.desc = "Invalid trade volume";
            info.level = LEVEL_WARNING;
            break;
        case ERR_MARKET_CLOSED:
            info.desc = "Market is closed";
            info.level = LEVEL_ERROR;
            break;
        case ERR_TRADE_DISABLED:
            info.desc = "Trade is disabled";
            info.level = LEVEL_ERROR;
            break;
        case ERR_NOT_ENOUGH_MONEY:
            info.desc = "Not enough money";
            info.level = LEVEL_ERROR;
            break;
        case ERR_PRICE_CHANGED:
            info.desc = "Price changed";
            info.level = LEVEL_WARNING;
            break;
        case ERR_OFF_QUOTES:
            info.desc = "Off quotes";
            info.level = LEVEL_WARNING;
            break;
        case ERR_BROKER_BUSY:
            info.desc = "Broker is busy";
            info.level = LEVEL_WARNING;
            break;
        case ERR_REQUOTE:
            info.desc = "Requote";
            info.level = LEVEL_WARNING;
            break;
        case ERR_ORDER_LOCKED:
            info.desc = "Order is locked";
            info.level = LEVEL_WARNING;
            break;
        case ERR_LONG_POSITIONS_ONLY_ALLOWED:
            info.desc = "Long positions only allowed";
            info.level = LEVEL_WARNING;
            break;
        case ERR_TOO_MANY_REQUESTS:
            info.desc = "Too many requests";
            info.level = LEVEL_WARNING;
            break;
        case ERR_TRADE_MODIFY_DENIED:
            info.desc = "Modification denied because order too close to market";
            info.level = LEVEL_WARNING;
            break;
        case ERR_TRADE_CONTEXT_BUSY:
            info.desc = "Trade context is busy";
            info.level = LEVEL_WARNING;
            break;
        case ERR_TRADE_EXPIRATION_DENIED:
            info.desc = "Expirations are denied by broker";
            info.level = LEVEL_WARNING;
            break;
        case ERR_TRADE_TOO_MANY_ORDERS:
            info.desc = "The amount of open and pending orders has reached the limit set by the broker";
            info.level = LEVEL_ERROR;
            break;
        case ERR_TRADE_HEDGE_PROHIBITED:
            info.desc = "An attempt to open a position opposite to the existing one when hedging is disabled";
            info.level = LEVEL_ERROR;
            break;
        case ERR_TRADE_PROHIBITED_BY_FIFO:
            info.desc = "An attempt to close a position contravening the FIFO rule";
            info.level = LEVEL_WARNING;
            break;
        //--- MQL4 run time error codes
        case ERR_TRADE_NOT_ALLOWED:
            info.desc = "Trade is not allowed. Enable checkbox (Allow live trading) in the expert properties";
            info.level = LEVEL_WARNING;
            break;
        case ERR_LONGS_NOT_ALLOWED:
            info.desc = "Longs are not allowed. Check the expert properties";
            info.level = LEVEL_ERROR;
            break;
        case ERR_SHORTS_NOT_ALLOWED:
            info.desc = "Shorts are not allowed. Check the expert properties";
            info.level = LEVEL_ERROR;
            break;
#endif

        //---
        case ERR_INVALID_ORDER_TYPE:
            info.desc = "Invalid order type";
            info.level = LEVEL_ERROR;
            break;
        case ERR_INVALID_SYMBOL_NAME:
            info.desc = "Invalid symbol name";
            info.level = LEVEL_ERROR;
            break;
        case ERR_INVALID_EXPIRATION_TIME:
            info.desc = "Invalid expiration time";
            info.level = LEVEL_ERROR;
            break;
        case ERR_ORDER_SELECT:
            info.desc = "Error function OrderSelect()";
            info.level = LEVEL_ERROR;
            break;
            //---

        default:
            info.desc = "Unknown error " + IntegerToString(info.code);
            return (false);
        }

        return (true);
    }
    /**
     * @brief Get the error description.
     * 
     * @param errorCode Error code.
     * @return Value of string type. 
     */
    string GetErrorDescription(const int errorCode)
    {
        ErrorInfo info;
        info.code = errorCode;

        GetErrorInfo(info);

        return (info.desc);
    }
    /**
     * @brief Get the error level description.
     * 
     * @param errorCode Error code.
     * @return Return the value of ENUM_ERROR_LEVEL enum.
     */
    ENUM_ERROR_LEVEL GetErrorLevel(const int errorCode)
    {
        ErrorInfo info;
        info.code = errorCode;

        GetErrorInfo(info);
        return (info.level);
    }
    /**
     * @brief Print error description to terminal. 
     * 
     * @param errorCode Error code
     * @return Return the value of ENUM_ERROR_LEVEL enum. 
     */
    ENUM_ERROR_LEVEL PrintError(int errorCode)
    {
        ErrorInfo info;
        info.code = errorCode;
        //---
        GetErrorInfo(info);
        //---
        printf("Error: %s", info.desc);
        //---
        return (info.level);
    }
    /**
     * @brief Convert enum ENUM_CHAT_ACTION to string type
     * 
     * @param action Input action
     * @return Value of string type. 
     */
    string ChatActionToString(const ENUM_CHAT_ACTION action)
    {
        string result = EnumToString(action);
        result = StringSubstr(result, 7);
        StringToLower(result);
        return (result);
    }
}