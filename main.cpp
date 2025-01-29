#include <zlib.h>

#include <cstdint>
#include <cstdlib>
#include <format>
#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>
#include <ranges>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#endif

const char *PROTO_PREFIX = "accessclient://";

struct Config {
  std::vector<std::string> options;
  bool debug;
};

Config g_config{{}, false};

std::vector<uint8_t> base64Decode(const std::string &encoded) {
  static constexpr unsigned char base64_table[256] = {
      /* Table initialization for Base64 decoding */
      64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64,
      64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64,
      64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 62, 64, 64, 64, 63,
      52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 64, 64, 64, 64, 64, 64,
      64, 0,  1,  2,  3,  4,  5,  6,  7,  8,  9,  10, 11, 12, 13, 14,
      15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 64, 64, 64, 64, 64,
      64, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
      41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 64, 64, 64, 64, 64};

  if (encoded.size() % 4 != 0)
    throw std::invalid_argument(
        "Invalid Base64 input: Length must be a multiple of 4");

  std::vector<uint8_t> decoded;
  size_t length = encoded.size();
  int val = 0;
  int valb = -8;

  for (unsigned char c : encoded) {
    if (base64_table[c] == 64) break;
    val = (val << 6) + base64_table[c];
    valb += 6;
    if (valb >= 0) {
      decoded.push_back((val >> valb) & 0xFF);
      valb -= 8;
    }
  }
  return decoded;
}

std::string zlibDecompress(const std::vector<uint8_t> &compressed) {
  z_stream zs{};
  if (inflateInit(&zs) != Z_OK)
    throw std::runtime_error("Failed to initialize zlib");
  zs.next_in = const_cast<Bytef *>(compressed.data());
  zs.avail_in = compressed.size();

  int ret;
  char buffer[32768];
  std::string decompressed;

  do {
    zs.next_out = reinterpret_cast<Bytef *>(buffer);
    zs.avail_out = sizeof(buffer);

    ret = inflate(&zs, 0);
    if (decompressed.size() < zs.total_out) {
      decompressed.append(buffer, zs.total_out - decompressed.size());
    }
  } while (ret == Z_OK);

  if (ret != Z_STREAM_END)
    throw std::runtime_error("Failed to decompress zlib data");

  inflateEnd(&zs);
  return decompressed;
}

void readConfig(const std::string &file) noexcept {
  using json = nlohmann::json;

  std::vector<std::string> opts;
  bool debug{false};

  std::ifstream config(file);
  if (!config.is_open()) return;

  json jsonData;
  config >> jsonData;

  try {
    opts = jsonData["options"].get<std::vector<std::string>>();
    debug = jsonData["debug"].get<bool>();
  } catch (const std::exception &ex) {
    std::cerr << "Error reading config file: " << ex.what() << std::endl;
    config.close();
    return;
  }

  g_config.options = std::move(opts);
  g_config.debug = debug;

  config.close();
}

void dumpPayload(const std::string &payload) {
  std::ofstream dump("payload.json");
  if (dump.is_open()) {
    dump << payload;
    dump.close();
  } else {
    throw std::runtime_error("Failed to dump payload");
  }
}

void launchSSH(const std::string &user, const std::string &host,
               const std::string &port,
               const std::vector<std::string> &ssh_options = {}) {
  std::string ssh_command = std::format(
      "ssh {} {}@{} -p {}",
      ssh_options | std::views::join_with(' ') | std::ranges::to<std::string>(),
      user, host, port);

  // This is required by Win32 API
  std::vector<char> command(ssh_command.begin(), ssh_command.end());
  command.push_back('\0');

  STARTUPINFO si = {sizeof(STARTUPINFO)};
  PROCESS_INFORMATION pi;
  if (!CreateProcess(NULL, command.data(), NULL, NULL, FALSE,
                     CREATE_NEW_CONSOLE, NULL, NULL, &si, &pi)) {
    std::cerr << "Failed to launch SSH command: " << GetLastError()
              << std::endl;
  } else {
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
  }
}

void copyPwdToClipboard(const std::string &pwd) {
  if (OpenClipboard(nullptr)) {
    EmptyClipboard();
    HGLOBAL hGlob = GlobalAlloc(GMEM_FIXED, pwd.size() + 1);
    if (hGlob) {
      memcpy(GlobalLock(hGlob), pwd.c_str(), pwd.size() + 1);
      GlobalUnlock(hGlob);
      SetClipboardData(CF_TEXT, hGlob);
    }
    CloseClipboard();
    if (hGlob) GlobalFree(hGlob);
  } else {
    throw std::runtime_error("Failed to open clipboard");
  }
}

int main(int argc, char *argv[]) {
  using json = nlohmann::json;

  if (argc != 2) {
    std::cerr << std::format("Fork Bao Lei\nUsage: {} PAYLOAD", argv[0])
              << std::endl;
    std::cerr << "Usage: " << argv[0] << " PAYLOAD" << std::endl;
    return 1;
  }

  // Load configuration
  readConfig("config.json");

  try {
    std::string payload(argv[1] + strlen(PROTO_PREFIX));

    // Decode Base64 and decompress zlib data
    std::vector<uint8_t> decodedData = base64Decode(payload);
    std::string decompressedData = zlibDecompress(decodedData);

    if (g_config.debug) dumpPayload(decompressedData);

    // Parse JSON data
    json jsonData = json::parse(decompressedData);
    std::string app = jsonData["app"];

    if (app != "putty")
      throw std::runtime_error("Unsupported application: " + app +
                               ". Please use putty.");

    std::string user = jsonData["un"];
    std::string host = jsonData["hn"];
    std::string port = jsonData["pn"];
    std::string pass = jsonData["pw"];

    // Print and copy password to clipboard
    std::cout << std::format("Connection Info:\nssh {}@{}:{}\nPassword: {}",
                             user, host, port, pass)
              << std::endl;

    // Not critical, just print a warning
    try {
      copyPwdToClipboard(pass);
      std::cout << "Password copied to clipboard" << std::endl;
    } catch (const std::exception &ex) {
      std::cerr << "Failed to copy password to clipboard: " << ex.what()
                << std::endl;
    }

    // Launch SSH command
    launchSSH(user, host, port, g_config.options);

  } catch (const std::exception &ex) {
    std::cerr << "Error: " << ex.what() << std::endl;
    if (g_config.debug) std::system("pause");
    return 1;
  }

  return 0;
}
