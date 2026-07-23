#include <windows.h>
#include <stdio.h>
#include <string.h>

HINSTANCE WINAPI ShellExecuteA(HWND hwnd, LPCSTR lpOperation, LPCSTR lpFile, LPCSTR lpParameters, LPCSTR lpDirectory, INT nShowCmd);

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    char appDir[MAX_PATH];
    char ollamaPath[MAX_PATH];
    char pythonPath[MAX_PATH];
    char modelsDir[MAX_PATH];
    char tempDir[MAX_PATH];
    char logsDir[MAX_PATH];
    char fontsDir[MAX_PATH];
    char staticDir[MAX_PATH];
    char ollamaLogPath[MAX_PATH];
    char serverLogPath[MAX_PATH];

    GetModuleFileNameA(NULL, appDir, MAX_PATH);
    char *lastSlash = strrchr(appDir, '\\');
    if (lastSlash) *lastSlash = '\0';

    snprintf(ollamaPath,    MAX_PATH, "%s\\bin\\ollama.exe", appDir);
    snprintf(pythonPath,    MAX_PATH, "%s\\bin\\python\\python.exe", appDir);
    snprintf(modelsDir,     MAX_PATH, "%s\\models", appDir);
    snprintf(tempDir,       MAX_PATH, "%s\\temp", appDir);
    snprintf(logsDir,       MAX_PATH, "%s\\logs", appDir);
    snprintf(fontsDir,      MAX_PATH, "%s\\fonts", appDir);
    snprintf(staticDir,     MAX_PATH, "%s\\static", appDir);
    snprintf(ollamaLogPath, MAX_PATH, "%s\\ollama.log", logsDir);
    snprintf(serverLogPath, MAX_PATH, "%s\\server.log", logsDir);

    CreateDirectoryA(tempDir, NULL);
    CreateDirectoryA(logsDir, NULL);

    WinExec("taskkill /F /IM ollama.exe /IM python.exe", SW_HIDE);
    Sleep(400);

    char pyPathEnv[MAX_PATH * 3];
    snprintf(pyPathEnv, sizeof(pyPathEnv), "%s;%s\\bin\\python;%s\\bin\\python\\Lib\\site-packages", appDir, appDir, appDir);

    SetEnvironmentVariableA("PYTHONPATH", pyPathEnv);
    SetEnvironmentVariableA("OLLAMA_MODELS", modelsDir);
    SetEnvironmentVariableA("OLLAMA_HOST", "127.0.0.1:11435");
    SetEnvironmentVariableA("IMPCON_OLLAMA_URL", "http://127.0.0.1:11435");
    SetEnvironmentVariableA("IMPCON_STATIC", staticDir);
    SetEnvironmentVariableA("IMPCON_TEMP", tempDir);
    SetEnvironmentVariableA("IMPCON_LOGS", logsDir);
    SetEnvironmentVariableA("IMPCON_FONTS", fontsDir);
    SetEnvironmentVariableA("IMPCON_PORT", "8500");

    SECURITY_ATTRIBUTES sa;
    sa.nLength = sizeof(sa);
    sa.bInheritHandle = TRUE;
    sa.lpSecurityDescriptor = NULL;

    // 1. Start Ollama with output redirected to logs\ollama.log
    HANDLE hOllamaLog = CreateFileA(ollamaLogPath, GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);

    STARTUPINFOA siOllama;
    PROCESS_INFORMATION piOllama;
    ZeroMemory(&siOllama, sizeof(siOllama));
    siOllama.cb = sizeof(siOllama);
    siOllama.dwFlags = STARTF_USESHOWWINDOW;
    siOllama.wShowWindow = SW_HIDE;

    if (hOllamaLog != INVALID_HANDLE_VALUE) {
        siOllama.dwFlags |= STARTF_USESTDHANDLES;
        siOllama.hStdOutput = hOllamaLog;
        siOllama.hStdError  = hOllamaLog;
    }

    char ollamaCmd[MAX_PATH + 30];
    snprintf(ollamaCmd, sizeof(ollamaCmd), "\"%s\" serve", ollamaPath);
    CreateProcessA(NULL, ollamaCmd, NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, appDir, &siOllama, &piOllama);

    // 2. Start Python server with output redirected to logs\server.log
    HANDLE hServerLog = CreateFileA(serverLogPath, GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);

    STARTUPINFOA siPy;
    PROCESS_INFORMATION piPy;
    ZeroMemory(&siPy, sizeof(siPy));
    siPy.cb = sizeof(siPy);
    siPy.dwFlags = STARTF_USESHOWWINDOW;
    siPy.wShowWindow = SW_HIDE;

    if (hServerLog != INVALID_HANDLE_VALUE) {
        siPy.dwFlags |= STARTF_USESTDHANDLES;
        siPy.hStdOutput = hServerLog;
        siPy.hStdError  = hServerLog;
    }

    char pyCmd[MAX_PATH * 2 + 60];
    snprintf(pyCmd, sizeof(pyCmd), "\"%s\" -m uvicorn app:app --host 0.0.0.0 --port 8500", pythonPath);
    CreateProcessA(NULL, pyCmd, NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, appDir, &siPy, &piPy);

    Sleep(3000);
    ShellExecuteA(NULL, "open", "http://localhost:8500", NULL, NULL, SW_SHOWNORMAL);

    WaitForSingleObject(piPy.hProcess, INFINITE);

    TerminateProcess(piOllama.hProcess, 0);
    CloseHandle(piPy.hProcess);
    CloseHandle(piPy.hThread);
    CloseHandle(piOllama.hProcess);
    CloseHandle(piOllama.hThread);

    if (hOllamaLog != INVALID_HANDLE_VALUE) CloseHandle(hOllamaLog);
    if (hServerLog != INVALID_HANDLE_VALUE) CloseHandle(hServerLog);

    return 0;
}
