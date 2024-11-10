x=linspace(0,2*pi,100);
 y=sin(x); z=cos(x);   
 a=sin(x).*cos(x);b=sin(x)./(cos(x)+eps)
 subplot(2,2,1);plot(x,y),title('sin(x)')
 subplot(2,2,2);plot(x,z),title('cos(x)')
 subplot(2,2,3);plot(x,a),title('sin(x)cos(x)')
 subplot(2,2,4);plot(x,b),title('sin(x)/cos(x)')

