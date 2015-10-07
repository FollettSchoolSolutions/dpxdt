FROM ubuntu:14.04
# I cheated here; I previously had done all the work on another VM w/ubuntu
# 14.04 to build phantomjs 2 from source
# In the future, hopefully the binary will be more easily available
# but currently there is a defect that is preventing people from 
# making it easily available to the software repositories
RUN apt-get update && apt-get install -y build-essential g++ flex bison gperf ruby perl \
  libsqlite3-dev libfontconfig1-dev libicu-dev libfreetype6 libssl-dev \
  libpng-dev libjpeg-dev python libx11-dev libxext-dev curl \
  imagemagick
#Install python related dependencies
RUN curl https://bootstrap.pypa.io/get-pip.py | python
RUN pip install virtualenv

COPY phantomjs /usr/bin/phantomjs 
RUN chmod 755 /usr/bin/phantomjs
COPY . /usr/local/dpxdt/

WORKDIR /usr/local/dpxdt
RUN ["virtualenv", "/usr/local/dpxdt/"]
RUN ["/bin/bash", "-c", "source /usr/local/dpxdt/bin/activate"]
RUN pip install -r /usr/local/dpxdt/requirements.txt
RUN pip install -e /usr/local/dpxdt/
RUN pip install pymysql

EXPOSE 5000
ENTRYPOINT ["/usr/local/dpxdt/run_combined.sh"]
