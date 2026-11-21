#ifndef MEMO_MANAGERS_LOGGING_MANAGER_MQH
#define MEMO_MANAGERS_LOGGING_MANAGER_MQH

#include <MEMO\Core\Types.mqh>

class CLoggingManager
{
private:
   int    m_handle;
   string m_file_name;
   bool   m_debug;

   void Write(const string level,
              const string component,
              const string symbol,
              const string stage,
              const string verdict,
              const double score,
              const string message)
   {
      const string stamp = TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS);
      PrintFormat("[MEMO][%s][%s][%s] %s", level, component, verdict, message);

      if(m_handle == INVALID_HANDLE)
         return;

      FileSeek(m_handle, 0, SEEK_END);
      FileWrite(m_handle, stamp, level, component, symbol, stage, verdict, DoubleToString(score, 2), message);
      FileFlush(m_handle);
   }

public:
   CLoggingManager()
   {
      m_handle = INVALID_HANDLE;
      m_file_name = "";
      m_debug = false;
   }

   bool Init(const string file_name, const bool debug_mode)
   {
      m_file_name = file_name;
      m_debug = debug_mode;
      m_handle = FileOpen(m_file_name, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ';');

      if(m_handle == INVALID_HANDLE)
      {
         PrintFormat("[MEMO][ERROR][LoggingManager] Unable to open log file %s. Error=%d", m_file_name, GetLastError());
         return false;
      }

      if(FileSize(m_handle) == 0)
         FileWrite(m_handle, "time", "level", "component", "symbol", "stage", "verdict", "score", "message");

      FileSeek(m_handle, 0, SEEK_END);
      Info("LoggingManager", "MEMO decision log online: " + m_file_name);
      return true;
   }

   void Close()
   {
      if(m_handle != INVALID_HANDLE)
      {
         Info("LoggingManager", "MEMO decision log closing");
         FileClose(m_handle);
         m_handle = INVALID_HANDLE;
      }
   }

   void Info(const string component, const string message)
   {
      Write("INFO", component, "", "", "OK", 0.0, message);
   }

   void Error(const string component, const string message)
   {
      Write("ERROR", component, "", "", "FAIL", 0.0, message);
   }

   void Debug(const string component, const string message)
   {
      if(m_debug)
         Write("DEBUG", component, "", "", "DEBUG", 0.0, message);
   }

   void Decision(const string component,
                 const string symbol,
                 const string stage,
                 const string verdict,
                 const double score,
                 const string message)
   {
      Write("DECISION", component, symbol, stage, verdict, score, message);
   }
};

#endif
