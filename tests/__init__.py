# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import appsettings2
import hanaro

hanaro.configure_logging(
    appsettings2.get_configuration()
)
