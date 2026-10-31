from django.core.mail.backends import console


class ConsoleEmailBackend(console.EmailBackend):
    """Django's console backend, but a stdout that cannot encode a character (Windows cp1252 and the rupee sign)
    prints an escaped copy instead of raising, so a dev/demo machine never turns an invoice email into a failure."""

    def write_message(self, message):
        try:
            super().write_message(message)
        except UnicodeEncodeError:
            text = message.message().as_string()
            self.stream.write(text.encode("ascii", "backslashreplace").decode("ascii") + "\n" + "-" * 79 + "\n")
