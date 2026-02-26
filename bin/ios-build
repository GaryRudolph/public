#!/bin/zsh
#set -x
set -e
set -o pipefail
WORKSPACE="OptimalTicketing.xcworkspace"
DEFAULT_OS_VERSION="16.2"

usage() {
  echo ""
  echo "usage: test.sh <SCHEME> [OS_VERSION]"
  exit 1
}

if [ -z "${1+x}" ]; then
  echo "SCHEME was not passed as a parameter"
  usage
else
  SCHEME=$1
fi

if [ -z "${2+x}" ]; then
  echo "OS_VERSION was not passed as a parameter using ${DEFAULT_OS_VERSION}"
  OS_VERSION="${DEFAULT_OS_VERSION}"
else
  OS_VERSION="${2}"
fi

SDK="iphonesimulator${OS_VERSION}"
PLATFORM="platform=iOS Simulator,OS=${OS_VERSION},name=iPhone 14"

BUILD_PATH=.github/workflows/build/${SCHEME}
rm -fr ${BUILD_PATH} ${BUILD_ARCHIVE}
mkdir -p ${BUILD_PATH}
DERIVED_PATH=${BUILD_PATH}/derived
RESULT_PATH=${BUILD_PATH}/result
XCODEBUILD_OUTPUT="${BUILD_PATH}/xcodebuild.log"
XCPRETTY_OUTPUT="${BUILD_PATH}/xcpretty.log"
XCCOV_OUTPUT="${BUILD_PATH}/xccov.log"
BUILD_ARCHIVE=.github/workflows/build/${SCHEME}.tgz

echo "--------------------------------------------------------------------------------"
echo "Building SCHEME=${SCHEME}"
echo "================================================================================"
echo "BUILD_PATH=${BUILD_PATH}"
echo "DERIVED_PATH=${DERIVED_PATH}"
echo "RESULT_PATH=${RESULT_PATH}"
echo "XCODEBUILD_OUTPUT=${XCODEBUILD_OUTPUT}"
echo "XCPRETTY_OUTPUT=${XCPRETTY_OUTPUT}"
echo "XCCOV_OUTPUT=${XCCOV_OUTPUT}"
echo "BUILD_ARCHIVE=${BUILD_ARCHIVE}"
echo "--------------------------------------------------------------------------------"

xcodebuild -workspace ${WORKSPACE} -scheme ${SCHEME} -sdk ${SDK} -destination "${PLATFORM}" \
-derivedDataPath "${DERIVED_PATH}" -enableCodeCoverage YES -resultBundlePath "${RESULT_PATH}" \
clean build-for-testing test \
| tee "${XCODEBUILD_OUTPUT}" \
| xcpretty \
| tee "${XCPRETTY_OUTPUT}"
echo "Wrote xcodebuild output to ${XCODEBUILD_OUTPUT}"
echo "Wrote xcpretty output to ${XCPRETTY_OUTPUT}"

echo "--------------------------------------------------------------------------------"
echo "Code Coverage SCHEME=${SCHEME}"
echo "--------------------------------------------------------------------------------"

xcrun xccov view --report "${BUILD_PATH}/result.xcresult" \
| tee "${XCCOV_OUTPUT}"
echo "Wrote xccov output to ${XCCOV_OUTPUT}"

echo "--------------------------------------------------------------------------------"
echo "Archiving the build SCHEME=${SCHEME}"
echo "--------------------------------------------------------------------------------"

tar cfz "${BUILD_ARCHIVE}" -C "${BUILD_PATH}" .
echo "Archived build to ${BUILD_ARCHIVE}"

echo "--------------------------------------------------------------------------------"
echo "Completed SCHEME=${SCHEME}"
echo "Archived to ${BUILD_ARCHIVE}"
echo "--------------------------------------------------------------------------------"

exit 0
