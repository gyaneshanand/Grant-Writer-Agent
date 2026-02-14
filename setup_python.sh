#!/bin/bash

# Configuration
VERSION_PYTHON="3.11.9"
VERSION_LIBFFI="3.4.4"
VERSION_SQLITE="3450300"
VERSION_SQLITE_YEAR="2024"

# Using absolute paths is safer. valid for most cPanel users.
INSTALL_DIR="$HOME/python_local"
BUILD_DIR="$HOME/python_build"

# Ensure directories exist
mkdir -p "$INSTALL_DIR"
mkdir -p "$BUILD_DIR"

# Helper for downloading
download_file() {
    local url="$1"
    local filename="$2"
    if [ -f "$filename" ]; then
        echo "File $filename already exists, skipping download."
    else
        if command -v wget >/dev/null 2>&1; then
            wget "$url" -O "$filename"
        elif command -v curl >/dev/null 2>&1; then
            curl -L "$url" -o "$filename"
        else
            echo "Error: Neither wget nor curl found. Please download $url manually."
            exit 1
        fi
    fi
}

# 1. Install libffi
echo "--- Installing libffi $VERSION_LIBFFI ---"
cd "$BUILD_DIR"
download_file "https://github.com/libffi/libffi/releases/download/v$VERSION_LIBFFI/libffi-$VERSION_LIBFFI.tar.gz" "libffi-$VERSION_LIBFFI.tar.gz"

tar -xf "libffi-$VERSION_LIBFFI.tar.gz"
cd "libffi-$VERSION_LIBFFI"
./configure --prefix="$INSTALL_DIR" --disable-docs
make
make install

# 2. Install SQLite
echo "--- Installing SQLite $VERSION_SQLITE ---"
cd "$BUILD_DIR"
# SQLite download URL format: https://www.sqlite.org/2024/sqlite-autoconf-3450300.tar.gz
download_file "https://www.sqlite.org/$VERSION_SQLITE_YEAR/sqlite-autoconf-$VERSION_SQLITE.tar.gz" "sqlite-autoconf-$VERSION_SQLITE.tar.gz"

tar -xf "sqlite-autoconf-$VERSION_SQLITE.tar.gz"
cd "sqlite-autoconf-$VERSION_SQLITE"
./configure --prefix="$INSTALL_DIR"
make
make install


# 3. Prepare Flags
# libffi often puts headers in lib/libffi-X.Y.Z/include
# sqlite puts headers in include
export PKG_CONFIG_PATH="$INSTALL_DIR/lib/pkgconfig"
export LD_LIBRARY_PATH="$INSTALL_DIR/lib"
# Rpath ensures the python binary knows where to find libffi AND sqlite at runtime
export LDFLAGS="-L$INSTALL_DIR/lib -Wl,-rpath=$INSTALL_DIR/lib"
export CPPFLAGS="-I$INSTALL_DIR/include -I$INSTALL_DIR/lib/libffi-$VERSION_LIBFFI/include"

# 4. Install Python (Must be re-compiled to link against new libs)
echo "--- Installing Python $VERSION_PYTHON ---"
cd "$BUILD_DIR"
download_file "https://www.python.org/ftp/python/$VERSION_PYTHON/Python-$VERSION_PYTHON.tar.xz" "Python-$VERSION_PYTHON.tar.xz"

tar -xf "Python-$VERSION_PYTHON.tar.xz"
cd "Python-$VERSION_PYTHON"
# clean ensures we don't use cached build artifacts from previous run
make clean
# Explicitly pass flags to ensure they are picked up
./configure --prefix="$INSTALL_DIR" --enable-optimizations --with-ensurepip=install LDFLAGS="$LDFLAGS" CPPFLAGS="$CPPFLAGS"
make
make install

# 5. Create Virtual Environment
echo "--- Creating virtual environment ---"
# Assuming script is run from project root, or adjacent to it. 
# Adjust this path if needed.
PROJECT_ROOT="$HOME/Grant-Writer-Agent" 

if [ -d "$PROJECT_ROOT" ]; then
    cd "$PROJECT_ROOT"
    echo "Creating venv in $PROJECT_ROOT/venv..."
    rm -rf venv
    "$INSTALL_DIR/bin/python3" -m venv venv
    
    # Install requirements
    source venv/bin/activate
    pip install --upgrade pip
    if [ -f "requirements.txt" ]; then
        echo "--- Installing requirements ---"
        pip install -r requirements.txt
    else
        echo "Warning: requirements.txt not found in $PROJECT_ROOT"
    fi
else
    echo "Warning: Project directory $PROJECT_ROOT not found. Venv created in current dir."
    "$INSTALL_DIR/bin/python3" -m venv venv
fi

echo "========================================"
echo "          SETUP COMPLETE"
echo "========================================"
echo "To activate your new environment, run:"
echo "source $PROJECT_ROOT/venv/bin/activate"
