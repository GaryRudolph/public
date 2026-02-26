#!/bin/zsh
#set -x
set -e
set -o pipefail

EXECUTABLE=$0

usage() {
	echo ""
	echo "usage: ${EXECUTABLE} <FLAVOR> <BUILD_TYPE> <API_LEVEL>"
	echo " i.e.: ${EXECUTABLE} flipseats debug 33"
	exit 1
}

killAllEmulators() {
	echo "Killing all emulators"
	adb devices | grep "emulator-" | while read -r line ; do
		suffix="	device"
		emulatorInstanceName=${line%${suffix}}

		echo "Killing $emulatorInstanceName"
		adb -s ${emulatorInstanceName} emu kill
	done
}


if [ -z "${1+x}" ]; then
	echo "FLAVOR was not passed as a parameter"
	usage
else
	FLAVOR=$1
fi

if [ -z "${2+x}" ]; then
	echo "BUILD_TYPE was not passed as a parameter"
	usage
else
	BUILD_TYPE=$2
fi

if [ -z "${3+x}" ]; then
	echo "API_LEVEL was not passed as a parameter"
	usage
else
	API_LEVEL=$3
fi

VARIANT=${(C)FLAVOR}${(C)BUILD_TYPE}

if [ -z "${JAVA_HOME_11_X64+x}" ]; then
	echo "JAVA_HOME_11_X64 not set so using default JAVA_HOME=${JAVA_HOME}"
else
	JAVA_HOME=${JAVA_HOME_11_X64}
fi

BUILD_PATH=`pwd`/.github/workflows/build
GRADLE_OUTPUT=${BUILD_PATH}/gradle.log
BUILD_ARCHIVE=.github/workflows/build.tgz
EMULATOR_OUTPUT=${BUILD_PATH}/emulator.log
EMULATOR_NAME="androidTest${API_LEVEL}"

rm -fr "${BUILD_PATH}"
rm -fr "${BUILD_ARCHIVE}"
mkdir -p "${BUILD_PATH}"

ARCHITECTURE=`uname -m`
if [[ "${ARCHITECTURE}" == "arm64" ]]; then
	ABI="arm64-v8a"
else
	ABI="x86_64"
fi

PACKAGE="system-images;android-${API_LEVEL};google_apis;${ABI}"

echo "--------------------------------------------------------------------------------"
echo "Creating AVD PACKAGE=${PACKAGE}"
echo "--------------------------------------------------------------------------------"

echo "y" | sdkmanager --install "${PACKAGE}"

echo "Installed emulator, now creating AVD"

avdmanager -v create avd -f \
-n "${EMULATOR_NAME}" \
-k  "${PACKAGE}" \
-d pixel_6

echo "--------------------------------------------------------------------------------"
echo "Starting Emulator EMULATOR_NAME=${EMULATOR_NAME}"
echo "--------------------------------------------------------------------------------"

echo "Checking if acceleration is enabled"
echo "yes" | emulator -accel-check

echo "Starting the emulator"
emulator -avd "${EMULATOR_NAME}" \
-no-snapshot-save \
-no-window \
-no-audio \
-no-boot-anim \
-camera-front none \
-camera-back none \
-gpu swiftshader_indirect \
> "${EMULATOR_OUTPUT}" 2>&1 &

WAIT_TIMEOUT=600
KILL_TIMEOUT=$((WAIT_TIMEOUT + 60))
echo "Waiting for emulator to start for ${WAIT_TIMEOUT} seconds, kill after ${KILL_TIMEOUT} seconds"

START=`date +%s`
set +e
timeout -k ${KILL_TIMEOUT} ${WAIT_TIMEOUT} \
adb \
wait-for-device \
shell 'while [[ -z $(getprop sys.boot_completed) ]]; do echo -n "."; sleep 1; done;' \
input keyevent 82

TIMEOUT_STATUS=$?
set -e

echo -n "\n"

END=`date +%s`
EXECUTION=$((END - START))

if [[ ${TIMEOUT_STATUS} -eq 124 ]]; then
	echo "Emulator Timed out after ${WAIT_TIMEOUT} (${EXECUTION}) seconds"
	exit 1
elif [[ ${TIMEOUT_STATUS} -gt 0 ]]; then
	echo "Emulator Timeout exited with ${TIMEOUT_STATUS} (${WAIT_TIMEOUT}:${EXECUTION})"
	exit 1
fi

echo "Emulator booted ${EXECUTION} seconds after device was started"

echo "--------------------------------------------------------------------------------"
echo "Building VARIANT=${VARIANT}"
echo "================================================================================"
echo "FLAVOR=${FLAVOR}"
echo "BUILD_TYPE=${BUILD_TYPE}"
echo "BUILD_PATH=${BUILD_PATH}"
echo "--------------------------------------------------------------------------------"

./gradlew -PbuildDir="${BUILD_PATH}" \
--no-daemon \
clean \
:app:test${VARIANT}UnitTest \
:app:connected${VARIANT}AndroidTest \
:app:lint${VARIANT} \
| tee "${GRADLE_OUTPUT}"
echo "Wrote gradle output to ${GRADLE_OUTPUT}"

echo "--------------------------------------------------------------------------------"
echo "Killing emulators"
echo "--------------------------------------------------------------------------------"

killAllEmulators

echo "--------------------------------------------------------------------------------"
echo "Archiving the build VARIANT=${VARIANT}"
echo "--------------------------------------------------------------------------------"

tar cfz "${BUILD_ARCHIVE}" -C "${BUILD_PATH}" .
echo "\nArchived build to ${BUILD_ARCHIVE}"

echo "--------------------------------------------------------------------------------"
echo "Completed VARIANT=${VARIANT}"
echo "Archived to ${BUILD_ARCHIVE}"
echo "--------------------------------------------------------------------------------"

exit 0
