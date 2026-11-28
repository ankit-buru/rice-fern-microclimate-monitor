# Run at every build (see CMakeLists.txt): writes OUT as a header with GIT_VERSION = `git describe --always --dirty`
# of the source tree (e.g. "3661742", "3661742-dirty"), rewriting it only when it changed so nothing rebuilds needlessly.
execute_process(COMMAND git describe --always --dirty --abbrev=7 WORKING_DIRECTORY ${SRC}
                OUTPUT_VARIABLE v OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET RESULT_VARIABLE rc)
if(NOT rc EQUAL 0 OR v STREQUAL "")
  set(v "unknown")
endif()
set(text "#define GIT_VERSION \"${v}\"\n")
if(EXISTS ${OUT})
  file(READ ${OUT} old)
endif()
if(NOT "${old}" STREQUAL "${text}")
  file(WRITE ${OUT} "${text}")
endif()
