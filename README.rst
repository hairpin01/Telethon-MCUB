.. |tmcub_emoji| image:: https://raw.githubusercontent.com/hairpin01/Telethon-MCUB/v1/assets/emoji.webp
   :width: 32
   :alt: 🚀

|tmcub_emoji| Telethon-MCUB
===========================

Telethon-MCUB is a maintained Telethon fork for MCUB and userbot-oriented
workloads. The Python import path remains ``telethon``, but the package name
for installation and publishing is ``Telethon-MCUB``.

Installation
------------

Install the base package:

.. code-block:: sh

    pip install -U Telethon-MCUB

Install with optional extras:

.. code-block:: sh

    pip install -U "Telethon-MCUB[cryptg]"
    pip install -U "Telethon-MCUB[socks]"
    pip install -U "Telethon-MCUB[media]"
    pip install -U "Telethon-MCUB[speedups]"
    pip install -U "Telethon-MCUB[all]"

Optional extras:

* ``cryptg`` for faster encryption/decryption.
* ``socks`` for proxy support through ``python-socks[asyncio]``.
* ``media`` for image resizing and media metadata extraction via ``pillow`` and
  ``hachoir``.
* ``speedups`` for faster gzip handling through ``isal``.
* ``all`` to install every optional dependency listed above.

Quick Start
-----------

.. code-block:: python

    from telethon import TelegramClient, events, sync

    api_id = 12345
    api_hash = "0123456789abcdef0123456789abcdef"

    client = TelegramClient("session_name", api_id, api_hash)
    client.start()

    print(client.get_me().stringify())
    client.send_message("username", "Hello from Telethon-MCUB")

    @client.on(events.NewMessage(pattern="(?i)hi|hello"))
    async def handler(event):
        await event.respond("Hey!")

Fork Notes
----------

* The package is published as ``Telethon-MCUB``, but existing code should keep
  importing ``telethon``.
* MCUB-specific changes and release history are tracked in ``CHANGELOG.md``.
* Core Telethon concepts and API documentation are still largely applicable:
  https://docs.telethon.dev

Project Links
-------------

* Repository: https://github.com/hairpin01/Telethon-MCUB
* Issues: https://github.com/hairpin01/Telethon-MCUB/issues
* MCUB-fork: https://github.com/hairpin01/MCUB-fork
