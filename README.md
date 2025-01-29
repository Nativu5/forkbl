# ForkBL

I don't like bastion hosts (Baolei Ji). 

I mean, I hate the so-called "AccessClient" installed on my PC. So I wrote this tool to help me to access the internal network.

## Build

```powershell
mkdir build
cd build
cmake -D CMAKE_BUILD_TYPE=Release ..
cmake --build . --config Release
cpack
```

Find the generated `.zip` in the `build` directory.

## Usage

```powershell
powershell ./scripts/install.ps1
```

Then open the bastion host web page, it will call the `ForkBL.exe` to establish the connection.
