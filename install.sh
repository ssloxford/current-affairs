cd "$(dirname "$0")"

# Install packages
sudo apt update
sudo apt install python3-pip python3-venv build-essential tcpdump git maven

# Download submodules
if [ -d .git ]; then
    git submodule update --init --recursive || exit 1
else
    git init || exit 1
    # Delete folders if empty
    rmdir libs/V2GDecoder
    rmdir open-plc-utils
    # Pull modules
    git submodule add https://github.com/FlUxIuS/V2Gdecoder libs/V2GDecoder || exit 1
    git submodule add https://github.com/ssloxford/open-plc-utils open-plc-utils || exit 1
fi;
cd libs/V2GDecoder || exit 1

# Apply patch
git stash
git reset --hard 6c26c817 || exit 1
git apply ../V2GDecoder.patch || exit 1

# Build V2GDecoder
mvn compile assembly:single || exit 1

# Build open-plc-utils
cd ../../open-plc-utils || exit 1
make clean || exit 1
make || exit 1

# Copy built files
cd .. || exit 1
chmod +x copy_builds.sh
./copy_builds.sh || exit 1

# Create venv
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt

echo 'Install successful. Run "source venv/bin/activate"'