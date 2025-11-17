curl -sk https://sharenest.adabala.com/api/health
sudo systemctl status sharenest --no-pager -l
tail -n 200 /opt/sharenest/logs/app.log
sudo tail -n 200 /var/log/nginx/sharenest.error.log
