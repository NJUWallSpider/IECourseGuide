
x=[1:1:100];
subplot(2,3,1);
plot(x,x.^3);
grid on;
title 'plot-y=x^3';

subplot(2,3,2);
loglog(x,x.^3);
grid on;
title 'loglog-logy=3logx';

subplot(2,3,3);
plotyy(x,x.^3,x,x);
grid on;
title 'plotyy-y=x^3,logy=3logx';



subplot(2,3,4);
semilogx(x,x.^3);
grid on;
title 'semilogx-y=3logx';

subplot(2,3,5);
semilogy(x,x.^3);
grid on;
title 'semilogy-logy=x^3';
hold off
