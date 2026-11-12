// USB descriptors: one CDC-ACM interface (the console). VID:PID 1209:0001 is the pid.codes test ID: fine for lab use,
// not for anything shipped. The serial number is the STM32 unique ID, so several boards can be told apart.
#include <string.h>
#include "tusb.h"
#include "hw.h"

static const tusb_desc_device_t desc_device = {
  .bLength = sizeof(tusb_desc_device_t), .bDescriptorType = TUSB_DESC_DEVICE, .bcdUSB = 0x0200,
  .bDeviceClass = TUSB_CLASS_MISC, .bDeviceSubClass = MISC_SUBCLASS_COMMON, .bDeviceProtocol = MISC_PROTOCOL_IAD,
  .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE, .idVendor = 0x1209, .idProduct = 0x0001, .bcdDevice = 0x0090,
  .iManufacturer = 1, .iProduct = 2, .iSerialNumber = 3, .bNumConfigurations = 1,
};
const uint8_t *tud_descriptor_device_cb(void) { return (const uint8_t *)&desc_device; }

enum { ITF_CDC = 0, ITF_CDC_DATA, ITF_TOTAL };
#define EP_NOTIF 0x81
#define EP_OUT   0x02
#define EP_IN    0x82
static const uint8_t desc_config[] = {
  TUD_CONFIG_DESCRIPTOR(1, ITF_TOTAL, 0, TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN, 0x00, 100),   // bus powered, 100 mA
  TUD_CDC_DESCRIPTOR(ITF_CDC, 4, EP_NOTIF, 8, EP_OUT, EP_IN, 64),
};
const uint8_t *tud_descriptor_configuration_cb(uint8_t index) { return desc_config; }

static const char *const strings[] = { NULL, "Rice TreeWeather", "TreeWeather bring-up console", NULL, "Console" };

const uint16_t *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
  static uint16_t buf[1 + 24];
  char serial[25];
  const char *s;
  unsigned n;
  if (index == 0) { buf[1] = 0x0409; n = 1; goto done; }                     // English (US)
  if (index >= sizeof strings / sizeof strings[0]) return NULL;
  s = strings[index];
  if (index == 3) {                                                           // serial = 96-bit unique ID in hex
    uint32_t uid[3]; hw_uid(uid);
    for (int w = 0; w < 3; w++)
      for (int d = 0; d < 8; d++) serial[w * 8 + d] = "0123456789ABCDEF"[(uid[w] >> (28 - 4 * d)) & 0xF];
    serial[24] = 0; s = serial;
  }
  n = strlen(s); if (n > 24) n = 24;
  for (unsigned i = 0; i < n; i++) buf[1 + i] = (uint8_t)s[i];
done:
  buf[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2 * n + 2));
  return buf;
}
