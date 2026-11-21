#include <Arrays\List.mqh>
#include <Arrays\ArrayString.mqh>
#include "CustomMessage.mqh"
#include "CustomChat.mqh"
#include "Common.mqh"
#include "Jason.mqh"
#include "netlib.mqh"

MqlNet mql_net;
namespace FxceTelegram
{
    /**
        * @brief Custom telegram bot API.
     * 
     */
    class CCustomBot
    {
    private:
        string _token;
        string _name;
        long _updateId;
        bool _firstRemove;
        CArrayString _usersFilter;

    public:
        CList _chats;

    private:
        /**
         * @brief Add a uchar array source to uchar array destination.
         * 
         * @param dest Array destination.
         * @param src Array source.
         */
        void ArrayAdd(uchar &dest[], const uchar &src[])
        {
            int src_size = ArraySize(src);
            if (src_size == 0)
                return;

            int dest_size = ArraySize(dest);
            ArrayResize(dest, dest_size + src_size, 500);
            ArrayCopy(dest, src, dest_size, 0, src_size);
        }
        /**
         * @brief Add the characters of a string to a uchar array destination.
         * 
         * @param dest Array destination.
         * @param text String text
         */
        void ArrayAdd(char &dest[], const string text)
        {
            int len = StringLen(text);
            if (len > 0)
            {
                uchar src[];
                for (int i = 0; i < len; i++)
                {
                    ushort ch = StringGetCharacter(text, i);

                    uchar array[];
                    int total = ShortToUtf8(ch, array);

                    int size = ArraySize(src);
                    ArrayResize(src, size + total);
                    ArrayCopy(src, array, size, 0, total);
                }
                ArrayAdd(dest, src);
            }
        }
        /**
         * @brief Url encoding a string.
         * 
         * @param text Input string.
         * @return Return value of string type.
         */
        string UrlEncode(const string text)
        {
            string result = NULL;
            int length = StringLen(text);
            for (int i = 0; i < length; i++)
            {
                ushort ch = StringGetCharacter(text, i);

                if ((ch >= 48 && ch <= 57) ||  // 0-9
                    (ch >= 65 && ch <= 90) ||  // A-Z
                    (ch >= 97 && ch <= 122) || // a-z
                    (ch == '!') || (ch == '\'') || (ch == '(') ||
                    (ch == ')') || (ch == '*') || (ch == '-') ||
                    (ch == '.') || (ch == '_') || (ch == '~'))
                {
                    result += ShortToString(ch);
                }
                else
                {
                    if (ch == ' ')
                        result += ShortToString('+');
                    else
                    {
                        uchar array[];
                        int total = ShortToUtf8(ch, array);
                        for (int k = 0; k < total; k++)
                            result += StringFormat("%%%02X", array[k]);
                    }
                }
            }
            return result;
        }
        /**
         * @brief URL decoding a string.
         * 
         * @param text Input text.
         * @return Return a value of string type.
         */
        string UrlDecode(string text)
        {
            //--- replace \n
            StringReplace(text, "\n", ShortToString(0x0A));

            //--- replace \u0000
            int haut = 0;
            int pos = StringFind(text, "\\u");
            while (pos != -1)
            {
                string strcode = StringSubstr(text, pos, 6);
                string strhex = StringSubstr(text, pos + 2, 4);

                StringToUpper(strhex);

                int total = StringLen(strhex);
                int result = 0;
                for (int i = 0, k = total - 1; i < total; i++, k--)
                {
                    int coef = (int)pow(2, 4 * k);
                    ushort ch = StringGetCharacter(strhex, i);
                    if (ch >= '0' && ch <= '9')
                        result += (ch - '0') * coef;
                    if (ch >= 'A' && ch <= 'F')
                        result += (ch - 'A' + 10) * coef;
                }

                if (haut != 0)
                {
                    if (result >= 0xDC00 && result <= 0xDFFF)
                    {
                        int dec = ((haut - 0xD800) << 10) + (result - 0xDC00); //+0x10000;
                        StringReplace(text, pos, 6, ShortToString((ushort)dec));
                        haut = 0;
                    }
                    else
                    {
                        //--- error: Second byte out of range
                        haut = 0;
                    }
                }
                else
                {
                    if (result >= 0xD800 && result <= 0xDBFF)
                    {
                        haut = result;
                        StringReplace(text, pos, 6, "");
                    }
                    else
                    {
                        StringReplace(text, pos, 6, ShortToString((ushort)result));
                    }
                }

                pos = StringFind(text, "\\u", pos);
            }
            return text;
        }
        /**
        * @brief Post a HTTP request.
        * 
        * @param out Response content.
        * @param url URL.
        * @param params Parameters.
        * @param timeout Request timeout
        * @return Return 0 in case successful, otherwise return an user error code.
        */
        int PostRequest(string &out, const string url, const string headers, const string params, const int timeout = 5000)
        {
            uchar data[];
            int data_size = StringLen(params);
            StringToCharArray(params, data, 0, data_size);
            return PostRequest(out, url, headers, data, timeout);
        }

        int PostRequest(string &out, const string url, const string headers, const uchar &params[], const int timeout = 5000)
        {
            uchar result[];
            string resultHeaders;

            //--- application/x-www-form-urlencoded
            int res = WebRequest("POST", url, headers, timeout, params, result, resultHeaders);
            if (res == 200) //OK
            {
                //--- delete BOM
                int startIndex = 0;
                int size = ArraySize(result);
                for (int i = 0; i < fmin(size, 8); i++)
                {
                    if (result[i] == 0xef || result[i] == 0xbb || result[i] == 0xbf)
                        startIndex = i + 1;
                    else
                        break;
                }
                //---
                out = CharArrayToString(result, startIndex, WHOLE_ARRAY, CP_UTF8);
                return 0;
            }
            else
            {
                if (res == -1)
                {
                    return _LastError;
                }
                else
                {
                    //--- HTTP errors
                    if (res >= 100 && res <= 511)
                    {
                        out = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
                        Print(out);
                        return ERR_HTTP_ERROR_FIRST + res;
                    }
                    return res;
                }
            }

            return 0;
        }
        /**
         * @brief Convert a character to UTF8 code.
         * 
         * @param ch Input character.
         * @param out UTF8 output
         * @return Return size of output array.
         */
        int ShortToUtf8(const ushort ch, uchar &out[])
        {
            //---
            if (ch < 0x80)
            {
                ArrayResize(out, 1);
                out[0] = (uchar)ch;
                return 1;
            }
            //---
            if (ch < 0x800)
            {
                ArrayResize(out, 2);
                out[0] = (uchar)((ch >> 6) | 0xC0);
                out[1] = (uchar)((ch & 0x3F) | 0x80);
                return 2;
            }
            //---
            if (ch < 0xFFFF)
            {
                if (ch >= 0xD800 && ch <= 0xDFFF) //Ill-formed
                {
                    ArrayResize(out, 1);
                    out[0] = ' ';
                    return 1;
                }
                else if (ch >= 0xE000 && ch <= 0xF8FF) //Emoji
                {
                    int ch = 0x10000 | ch;
                    ArrayResize(out, 4);
                    out[0] = (uchar)(0xF0 | (ch >> 18));
                    out[1] = (uchar)(0x80 | ((ch >> 12) & 0x3F));
                    out[2] = (uchar)(0x80 | ((ch >> 6) & 0x3F));
                    out[3] = (uchar)(0x80 | ((ch & 0x3F)));
                    return 4;
                }
                else
                {
                    ArrayResize(out, 3);
                    out[0] = (uchar)((ch >> 12) | 0xE0);
                    out[1] = (uchar)(((ch >> 6) & 0x3F) | 0x80);
                    out[2] = (uchar)((ch & 0x3F) | 0x80);
                    return 3;
                }
            }
            ArrayResize(out, 3);
            out[0] = 0xEF;
            out[1] = 0xBF;
            out[2] = 0xBD;
            return 3;
        }
        /**
         * @brief Custom string repalcement function.
         * 
         * @param strVar String will be changed.
         * @param startPos The starting position of the replacement
         * @param length Number of characters to be replaced
         * @param replacement The string which 'strVar' will be replaced with.
         * @return Return the number of replaced characters. 
         */
        int StringReplace(string &strVar, const int startPos, const int length, const string replacement)
        {
            string temp = (startPos == 0) ? "" : StringSubstr(strVar, 0, startPos);
            temp += replacement;
            temp += StringSubstr(strVar, startPos + length);
            strVar = temp;
            return StringLen(replacement);
        }
        /**
         * @brief Bool type to string
         * 
         * @param value Input value
         * @return Return a value of string type. 
         */
        string BoolToString(const bool value)
        {
            if (value)
                return "true";
            return "false";
        }

    protected:
        /**
         * @brief Trimming a string
         * 
         * @param text Input
         * @return Return trimmed string
         */
        string StringTrim(string text)
        {
#ifdef __MQL4__
            text = StringTrimLeft(text);
            text = StringTrimRight(text);
#endif
#ifdef __MQL5__
            StringTrimLeft(text);
            StringTrimRight(text);
#endif
            return text;
        }

    public:
        /**
        * @brief Construct a new CCustomBot object
        * 
        */
        CCustomBot()
        {
            _token = NULL;
            _name = NULL;
            _updateId = 0;
            _firstRemove = true;
            _chats.Clear();
            _usersFilter.Clear();
        }
        /**
        * @brief Destroy the CCustomBot object
        * 
        */
        ~CCustomBot()
        {
            _chats.Clear();
            _usersFilter.Clear();
        }
        /**
        * @brief Get total chats
        * 
        * @return Return a value of int type.
        */
        int ChatsTotal()
        {
            return _chats.Total();
        }
        /**
        * @brief Set telegram bot token.
        * 
        * @param token Bot token.
        * @return Return 0 in case successful, otherwise return an user error code.
        */
        int Token(const string token)
        {
            string temp = StringTrim(token);
            if (temp == "")
                return ERR_TOKEN_ISEMPTY;
            //---
            _token = temp;
            return 0;
        }
        /**
        * @brief Filter User Name
        * 
        * @param usernames Input username
        */
        void UserNameFilter(const string usernames)
        {
            _usersFilter.Clear();

            //--- parsing
            string text = StringTrim(usernames);
            if (text == "")
                return;

            //---
            while (StringReplace(text, "  ", " ") > 0)
            {
            }

            StringReplace(text, ";", " ");
            StringReplace(text, ",", " ");

            //---
            string array[];
            int amount = StringSplit(text, ' ', array);
            for (int i = 0; i < amount; i++)
            {
                string username = StringTrim(array[i]);
                if (username != "")
                {
                    //--- remove first @
                    if (StringGetCharacter(username, 0) == '@')
                        username = StringSubstr(username, 1);

                    _usersFilter.Add(username);
                }
            }
        }
        /**
        * @brief Get bot name.
        * 
        * @return Return a value of string type.
        */
        string Name()
        {
            return _name;
        }
        /**
        * @brief Get bot info.
        * 
        * @return Return 0 in case successful, otherwise return an user error code.
        */
        int GetMe()
        {
            if (_token == NULL)
                return ERR_TOKEN_ISEMPTY;
            //---
            string out;
            //string url = StringFormat("%s/bot%s/getMe", TELEGRAM_BASE_URL, _token);
            string url = StringFormat("/bot%s/getMe", _token);
            string params = "";
            //int res = PostRequest(out, url, "", params, WEB_TIMEOUT);
            int res=-1;
            if(mql_net.Open(TELEGRAM_BASE_URL,TELEGRAM_PORT))
            {
            	bool rs=mql_net.Request("","POST",url,out,params,false,"");
            	if(rs)
            	{
            		CJAVal js(NULL, jtUNDEF);
	                //---
	                bool done = js.Deserialize(out);
	                if (!done)
	                    return ERR_JSON_PARSING;
	
	                //---
	                bool ok = js["ok"].ToBool();
	                if (!ok)
	                    return ERR_JSON_NOT_OK;
	
	                //---
	                if (_name == NULL)
                    _name = js["result"]["username"].ToStr();
                   res=0; 
            	}
            }
            return res;
        }
        /**
        * @brief Use this method to receive incoming updates.
        * 
        * @return Return 0 in case successful, otherwise return an user error code. 
        */
        int GetUpdates()
        {
            if (_token == NULL)
                return ERR_TOKEN_ISEMPTY;

            string out;
            string url = StringFormat("%s/bot%s/getUpdates", TELEGRAM_BASE_URL, _token);
            string params = StringFormat("offset=%d", _updateId);
            //---
            int res = PostRequest(out, url, "", params, WEB_TIMEOUT);
            if (res == 0)
            {
                //--- parse result
                CJAVal js(NULL, jtUNDEF);
                bool done = js.Deserialize(out);
                if (!done)
                    return ERR_JSON_PARSING;

                bool ok = js["ok"].ToBool();
                if (!ok)
                    return ERR_JSON_NOT_OK;
                ReceiveMessageChannel(js["result"].m_e);
                ReceiveMessageIndividual(js["result"].m_e);
            }

            return res;
        }

        void ReceiveMessageIndividual(CJAVal &messages[])
        {

            CCustomMessage msg;

            int total = ArraySize(messages);
            for (int i = 0; i < total; i++)
            {
                CJAVal item = messages[i];
                //---
                msg.UpdateId = item["update_id"].ToInt();
                //---
                msg.MessageId = item["message"]["message_id"].ToInt();
                msg.MessageDate = (datetime)item["message"]["date"].ToInt();
                //---
                msg.MessageText = item["message"]["text"].ToStr();
                msg.MessageText = UrlDecode(msg.MessageText);
                //---
                msg.FromId = item["message"]["from"]["id"].ToInt();

                msg.FromFirstName = item["message"]["from"]["first_name"].ToStr();
                msg.FromFirstName = UrlDecode(msg.FromFirstName);

                msg.FromLastName = item["message"]["from"]["last_name"].ToStr();
                msg.FromLastName = UrlDecode(msg.FromLastName);

                msg.FromUserName = item["message"]["from"]["username"].ToStr();
                msg.FromUserName = UrlDecode(msg.FromUserName);
                //---
                msg.ChatId = item["message"]["chat"]["id"].ToInt();

                msg.ChatFirstName = item["message"]["chat"]["first_name"].ToStr();
                msg.ChatFirstName = UrlDecode(msg.ChatFirstName);

                msg.ChatLastName = item["message"]["chat"]["last_name"].ToStr();
                msg.ChatLastName = UrlDecode(msg.ChatLastName);

                msg.ChatUserName = item["message"]["chat"]["username"].ToStr();
                msg.ChatUserName = UrlDecode(msg.ChatUserName);

                msg.ChatType = item["message"]["chat"]["type"].ToStr();

                _updateId = msg.UpdateId + 1;

                if (_firstRemove)
                    continue;

                //--- filter
                if (_usersFilter.Total() == 0 || (_usersFilter.Total() > 0 && _usersFilter.SearchLinear(msg.FromUserName) >= 0))
                {

                    //--- find the chat
                    int index = -1;
                    for (int j = 0; j < _chats.Total(); j++)
                    {
                        CCustomChat *chat = _chats.GetNodeAtIndex(j);
                        if (chat.Id == msg.ChatId)
                        {
                            index = j;
                            break;
                        }
                    }

                    //--- add new one to the chat list
                    if (index == -1)
                    {
                        _chats.Add(new CCustomChat);
                        CCustomChat *chat = _chats.GetLastNode();
                        chat.Id = msg.ChatId;
                        chat.Time = TimeLocal();
                        chat.State = 0;
                        chat.NewOne.MessageText = msg.MessageText;
                        chat.NewOne.Done = false;
                    }
                    //--- update chat message
                    else
                    {
                        CCustomChat *chat = _chats.GetNodeAtIndex(index);
                        chat.Time = TimeLocal();
                        chat.NewOne.MessageText = msg.MessageText;
                        chat.NewOne.Done = false;
                    }
                }
            }
            _firstRemove = false;
        }

        void ReceiveMessageChannel(CJAVal &messages[])
        {
            CCustomMessage msg;

            int total = ArraySize(messages);
            for (int i = 0; i < total; i++)
            {
                CJAVal item = messages[i];
                //---
                msg.UpdateId = item["update_id"].ToInt();
                //---
                msg.MessageDate = item["channel_post"]["message_id"].ToInt();
                msg.MessageDate = (datetime)item["channel_post"]["date"].ToInt();
                //---
                msg.MessageText = item["channel_post"]["text"].ToStr();
                msg.MessageText = UrlDecode(msg.MessageText);
                //---
                msg.MessageId = item["channel_post"]["id"].ToInt();
                //---
                msg.FromId = item["channel_post"]["sender_chat"]["title"].ToStr();
                msg.FromId = UrlDecode(msg.FromId);
                //---
                msg.FromUserName = item["channel_post"]["sender_chat"]["username"].ToStr();
                msg.FromUserName = UrlDecode(msg.FromUserName);
                //---
                msg.ChatType = item["channel_post"]["sender_chat"]["type"].ToStr();
                msg.ChatType = UrlDecode(msg.ChatType);
                //---s
                msg.ChatId = item["channel_post"]["sender_chat"]["id"].ToInt();
                //---
                msg.ChatLastName = item["channel_post"]["sender_chat"]["title"].ToStr();
                msg.ChatLastName = UrlDecode(msg.ChatLastName);
                //---
                // msg.ChatChannelUsername = item["channel_post"]["chat"]["username"].ToStr();
                // msg.ChatChannelUsername = UrlDecode(msg.ChatChannelUsername);
                //---
                // msg.ChatChannelType = item["channel_post"]["chat"]["type"].ToStr();

                _updateId = msg.UpdateId + 1;

                if (_firstRemove)
                    continue;

                //--- filter
                if (_usersFilter.Total() == 0 || (_usersFilter.Total() > 0 && _usersFilter.SearchLinear(msg.FromUserName) >= 0))
                {

                    //--- find the chat
                    int index = -1;
                    for (int j = 0; j < _chats.Total(); j++)
                    {
                        CCustomChat *chat = _chats.GetNodeAtIndex(j);
                        if (chat.Id == msg.ChatId)
                        {
                            index = j;
                            break;
                        }
                    }

                    //--- add new one to the chat list
                    if (index == -1)
                    {
                        _chats.Add(new CCustomChat);
                        CCustomChat *chat = _chats.GetLastNode();
                        chat.Id = msg.ChatId;
                        chat.Time = TimeLocal();
                        chat.State = 0;
                        chat.NewOne.MessageText = msg.MessageText;
                        chat.NewOne.Done = false;
                    }
                    //--- update chat message
                    else
                    {
                        CCustomChat *chat = _chats.GetNodeAtIndex(index);
                        chat.Time = TimeLocal();
                        chat.NewOne.MessageText = msg.MessageText;
                        chat.NewOne.Done = false;
                    }
                }
            }
            _firstRemove = false;
        }

        /**
        * @brief Sends a notification about user activity in a chat.
        * 
        * @param chatId Unique identifier for the target chat or username of the target channel.
        * @param action The action description.
        * @return Return 0 in case successful, otherwise return an user error code.  
        */
        int SendChatAction(const long chatId, const ENUM_CHAT_ACTION action)
        {
            if (_token == NULL)
                return ERR_TOKEN_ISEMPTY;
            string out;
            string url = StringFormat("/bot%s/sendChatAction", _token);
            string params = StringFormat("chat_id=%lld&action=%s", chatId, ChatActionToString(action));
            //int res = PostRequest(out, url, "", params, WEB_TIMEOUT);
            int res=-1;
            
            if(mql_net.Open(TELEGRAM_BASE_URL,TELEGRAM_PORT))
            {
            	bool rs=mql_net.Request("","POST",url,out,params,false,"");
            	if(rs) res=0;
            }
            
            return res;
        }
        /**
        * @brief Use this method to send photos.
        * 
        * @param chatId Unique identifier for the target chat or username of the target channel (in the format @channelusername).
        * @param photoId Photo to send, the name of the file can contain subfolders.
        *                The file is opened in the folder of the client terminal in the subfolder MQL5\Files.
        * @param caption Photo caption (may also be used when re-sending photos by file_id), 0-1024 characters.
        * @param commonFlag Location of the file in a shared folder for all client terminals \Terminal\Common\Files.
        * @param timeout Request timeout.
        * @return Return 0 in case successful, otherwise return an user error code.  
        */
        int SendPhoto(const string chatId, const string photoId, const string caption = NULL, const bool commonFlag = false, const ulong timeout = WEB_TIMEOUT)
        {
            ResetLastError();
            if (_token == NULL)
            {
                return ERR_TOKEN_ISEMPTY;
            }
            //--- copy file to memory buffer
            if (!FileIsExist(photoId, commonFlag))
            {
                return ERR_FILE_NOT_EXIST;
            }

            int flags = FILE_READ | FILE_BIN | FILE_SHARE_WRITE | FILE_SHARE_READ;
            if (commonFlag)
            {
                flags |= FILE_COMMON;
            }

            int file = FileOpen(photoId, flags);
            if (file == INVALID_HANDLE)
            {
                return _LastError;
            }

            int fileSize = (int)FileSize(file);
            uchar photo[];
            ArrayResize(photo, fileSize);
            FileReadArray(file, photo, 0, fileSize);
            FileClose(file);
            //--- create boundary: (data -> base64 -> 1024 bytes -> md5)
            uchar base64[];
            uchar key[];
            CryptEncode(CRYPT_BASE64, photo, key, base64);
            //---
            uchar temp[1024] = {0};
            ArrayCopy(temp, base64, 0, 0, 1024);
            //---
            uchar md5[];
            CryptEncode(CRYPT_HASH_MD5, temp, key, md5);
            //---
            string hash = NULL;
            int total = ArraySize(md5);
            for (int i = 0; i < total; i++)
                hash += StringFormat("%02X", md5[i]);
            hash = StringSubstr(hash, 0, 16);

            //--- WebRequest
            uchar result[];
            string resultHeaders;

            //string url = StringFormat("%s/bot%s/sendPhoto", TELEGRAM_BASE_URL, _token);
            string url = StringFormat("/bot%s/sendPhoto", _token);

            //--- 1
            char params[];

            //--- add chart_id
            ArrayAdd(params, "\r\n");
            ArrayAdd(params, "--" + hash + "\r\n");
            ArrayAdd(params, "Content-Disposition: form-data; name=\"chat_id\"\r\n");
            ArrayAdd(params, "\r\n");
            ArrayAdd(params, chatId);
            ArrayAdd(params, "\r\n");

            if (StringLen(caption) > 0)
            {
                ArrayAdd(params, "--" + hash + "\r\n");
                ArrayAdd(params, "Content-Disposition: form-data; name=\"caption\"\r\n");
                ArrayAdd(params, "\r\n");
                ArrayAdd(params, caption);
                ArrayAdd(params, "\r\n");
            }

            ArrayAdd(params, "--" + hash + "\r\n");
            ArrayAdd(params, "Content-Disposition: form-data; name=\"photo\"; filename=\"lampash.gif\"\r\n");
            ArrayAdd(params, "\r\n");
            ArrayAdd(params, photo);
            ArrayAdd(params, "\r\n");
            ArrayAdd(params, "--" + hash + "--\r\n");

            string headers = "Content-Type: multipart/form-data; boundary=" + hash + "\r\n";
            string out;

            //int res = PostRequest(out, url, headers, params, WEB_TIMEOUT);
            int res=-1;
            if(mql_net.Open(TELEGRAM_BASE_URL,TELEGRAM_PORT))
            {
            	bool rs=mql_net.Request2(headers,"POST",url,out,params,false,"");
            	if(rs)
            	{	res=0;}
            	else
            	{
            		CJAVal js(NULL, jtUNDEF);
	                bool done = js.Deserialize(out);
	                if (!done)
	                    return ERR_JSON_PARSING;
	
	                //--- get error description
	                bool ok = js["ok"].ToBool();
	                long err_code = js["error_code"].ToInt();
	                string err_desc = js["description"].ToStr();
            	}	
            }
            /*if (res != 0)
            {
                //--- parse result
                CJAVal js(NULL, jtUNDEF);
                bool done = js.Deserialize(out);
                if (!done)
                    return ERR_JSON_PARSING;

                //--- get error description
                bool ok = js["ok"].ToBool();
                long err_code = js["error_code"].ToInt();
                string err_desc = js["description"].ToStr();
            }*/
            //--- done
            return res;
        }
        /**
        * @brief Using for receive command.
        * 
        */
        virtual void ProcessMessages(void){};
        /**
        * @brief Use this method to send text messages
        * 
        * @param chatId Unique identifier for the target chat or username of the target channel (in the format @channelusername)
        * @param text Text of the message to be sent, 1-4096 characters after entities parsing
        * @param replyMarkup Additional interface options. A JSON-serialized object for an inline keyboard, custom reply keyboard, 
        *                    instructions to remove reply keyboard or to force a reply from the user.
        * @param asHTML Format message to HTML.
        * @param silently Disbale Notification.
        * @return Return 0 in case successful, otherwise return an user error code.   
        */
        int SendMessage(const string chatId, const string text, const string replyMarkup = NULL, const bool asHTML = false, const bool silently = false)
        {
            //--- check token
            if (_token == NULL)
                return ERR_TOKEN_ISEMPTY;

            string out;
            //string url = StringFormat("%s/bot%s/sendMessage", TELEGRAM_BASE_URL, _token);
            string headers = "Content-Type: application/json\r\nAccept: application/json\r\n";
            string url = StringFormat("/bot%s/sendMessage", _token);	
            
            string params = StringFormat("chat_id=%s&text=%s", chatId, UrlEncode(text));
            CJAVal my_json;
            my_json["chat_id"]=chatId;
				my_json["text"]=text;
 
            if (replyMarkup != NULL)
                my_json["reply_markup"]=replyMarkup;
            if (asHTML)
                my_json["parse_mode"]="HTML";
            if (silently)
            	 my_json["disable_notification"]="true";
            
            string string_json;
				my_json.Serialize(string_json);
				if(mql_net.Open(TELEGRAM_BASE_URL,TELEGRAM_PORT))
				{
					bool rs=mql_net.Request(headers,"POST",url,out,string_json,false,"");
					//Print("Kq: "+out);
					if(rs)
						return 0;
					else
						return -1;	
				}
            //return PostRequest(out, url, "", params, WEB_TIMEOUT);
            return -1;
        }
        /**
        * @brief Format rely keyboard markup.
        * 
        * @param keyboard Keyboard.
        * @param resize Using resize.
        * @param oneTime Show one time.
        * @return Return a value of string type. 
        */
        string ReplyKeyboardMarkup(const string keyboard, const bool resize, const bool oneTime)
        {
            return StringFormat("{\"keyboard\": %s, \"one_time_keyboard\": %s, \"resize_keyboard\": %s, \"selective\": false}", UrlEncode(keyboard), BoolToString(resize), BoolToString(oneTime));
        }
        /**
        * @brief Get parameter hide reply keyboard.
        * 
        * @return Return a value of string type.  
        */
        string ReplyKeyboardHide()
        {
            return "{\"hide_keyboard\": true}";
        }
        /**
        * @brief Get parameter force reply keyboard.
        * 
        * @return Return a value of string type.   
        */
        string ForceReply()
        {
            return "{\"force_reply\": true}";
        }
    };
}