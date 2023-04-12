Octopus EV Charge Slot Poller

This Python script polls the Octopus Energy API for available charging slots for electric vehicles and logs the information to both a MySQL database and an MQTT server.
Installation

    Clone this repository to your local machine.
    Install the required Python packages by running pip install -r requirements.txt.
    Set up a MySQL database and update the config.py file with your database details.
    Set up an MQTT server and update the config.py file with your MQTT server details.

Usage

To use the script, simply run python octopus_ev_charge_slot_poller.py. The script will run indefinitely, polling the Octopus Energy API every 5 minutes and logging any available charging slots to both the MySQL database and MQTT server.

You can stop the script at any time by pressing Ctrl + C.
Configuration

All configuration options can be found in the config.py file. You can update the following options:

    API_KEY: Your Octopus Energy API key.
    MYSQL_HOST: The hostname of your MySQL database.
    MYSQL_PORT: The port number of your MySQL database.
    MYSQL_USER: The username to use when connecting to your MySQL database.
    MYSQL_PASSWORD: The password to use when connecting to your MySQL database.
    MYSQL_DATABASE: The name of the MySQL database to use.
    MQTT_HOST: The hostname of your MQTT server.
    MQTT_PORT: The port number of your MQTT server.
    MQTT_USER: The username to use when connecting to your MQTT server.
    MQTT_PASSWORD: The password to use when connecting to your MQTT server.
    MQTT_TOPIC: The MQTT topic to publish charging slot information to.

License

This project is licensed under the MIT License - see the LICENSE file for details.
