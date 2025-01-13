#!/bin/bash

apt-get -y update
apt-get -y update; apt-get -y install gnupg
apt-get --assume-yes install wget
apt-get install -yqq unzip
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
apt-get -y update
apt-get install -y google-chrome-stable
#wget -q https://chromedriver.storage.googleapis.com/79.0.3945.36/chromedriver_linux64.zip
wget -q https://chromedriver.storage.googleapis.com/81.0.4044.69/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
mv chromedriver /usr/local/bin/chromedriver
chown root:root /usr/local/bin/chromedriver
chmod +x /usr/local/bin/chromedriver