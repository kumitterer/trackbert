# Trackbert

A simple Python script for tracking shipments, primarily through [KeyDelivery](https://kd100.com).

If your system provides `notify-send`, you will get a desktop notification when the status of your shipment changes.

Status information is stored in a SQLite database.

## Currently supported tracking providers

- [KeyDelivery](https://kd100.com) (paid, provides tracking for most carriers)
- [Austrian Post](https://www.post.at)

## Requirements

The script was developed and tested on Arch Linux using Python 3.11. The "Never" type hint is used, so I suppose it will not work on older Python versions. It should work on any Linux distribution. You can technically run it on Windows and macOS as well, but you will not get desktop notifications.

In order to get desktop notifications, you need to have `notify-send` installed. On Arch Linux, this is provided by the `libnotify` package. If your desktop environment does not provide a notification server, you have to install one yourself. How to do this is beyond the scope of this README.

## Installation

```bash
git clone https://kumig.it/kumitterer/trackbert.git
cd trackbert
python -m venv venv
source venv/bin/activate
pip install .
```

Then copy `config.dist.ini` to `config.ini` and fill in your KeyDelivery API details, which you can find in your [KeyDelivery API management](https://app.kd100.com/api-management). You can find your API key in your KeyDelivery account settings.

## Usage

First, assure that the virtual environment is activated:

```bash
source venv/bin/activate
```

To add a new shipment, run `trackbert --tracking-number <tracking-number> --carrier <carrier-id>`. Find the required carrier ID in the [KeyDelivery API management](https://app.kd100.com/api-management).

To run the main loop, run `trackbert`. This will check the status of all shipments every 5 minutes, and print the status to the console. If the status of a shipment changes, you will get a desktop notification.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
