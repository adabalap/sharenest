sudo systemctl daemon-reload
sudo systemctl enable sharenest
sudo systemctl restart sharenest
sudo systemctl status sharenest --no-pager -l
sudo ln -sf /etc/nginx/sites-available/sharenest.adabala.com /etc/nginx/sites-enabled/sharenest.adabala.com
sudo nginx -t
sudo systemctl reload nginx
