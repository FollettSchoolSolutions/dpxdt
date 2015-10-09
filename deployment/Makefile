all:

clean:
	rm -Rf sqlite_deploy

sqlite_deploy:
	rm -Rf sqlite_deploy
	cp -R -L sqlite sqlite_deploy
	cd sqlite_deploy && ./bootstrap.py
	rm sqlite_deploy/bootstrap.py
mysql_deploy:
	rm -Rf mysql_deploy
	cp -R -L mysql mysql_deploy
	cd mysql_deploy && ./bootstrap.py
	rm mysql_deploy/bootstrap.py
mysql_exists_deploy:
	rm -Rf mysql_deploy
	cp -R -L mysql mysql_deploy
	cd mysql_deploy && ./bootstrap.py --dbexists=true
	rm mysql_deploy/bootstrap.py
