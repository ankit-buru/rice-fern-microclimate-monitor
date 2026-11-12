// newlib-nano stubs: the firmware never uses file I/O (printing goes through vsnprintf + the console), but the
// C library still links these. Defining them here keeps the linker from warning that nosys's versions always fail.
#include <errno.h>
#include <sys/stat.h>

int _close(int fd) { (void)fd; errno = EBADF; return -1; }
int _lseek(int fd, int off, int whence) { (void)fd; (void)off; (void)whence; errno = ESPIPE; return -1; }
int _read(int fd, char *buf, int n) { (void)fd; (void)buf; (void)n; errno = EBADF; return -1; }
int _write(int fd, const char *buf, int n) { (void)fd; (void)buf; (void)n; errno = EBADF; return -1; }
int _fstat(int fd, struct stat *st) { (void)fd; st->st_mode = S_IFCHR; return 0; }
int _isatty(int fd) { (void)fd; return 1; }
