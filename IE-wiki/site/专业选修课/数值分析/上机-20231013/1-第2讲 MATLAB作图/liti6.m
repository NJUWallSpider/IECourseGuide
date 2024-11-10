x=linspace(0,2*pi,100);
y=sin(x);z=cos(x);
plot(x,y);
title('sin(x)');
pause   %暂时停止执行 MATLAB

figure(2);
plot(x,z);
title('cos(x)');
pause
