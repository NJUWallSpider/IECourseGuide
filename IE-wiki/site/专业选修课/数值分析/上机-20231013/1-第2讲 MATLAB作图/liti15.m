theta=linspace(0,2*pi),                         
rho=sin(2*theta).*cos(2*theta);
polar(theta,rho,'g')
title('Polar plot of sin(2*theta).*cos(2*theta)');