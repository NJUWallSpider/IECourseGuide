[x,y]=meshgrid(0:0.01:3);
z=180*exp(-((x.^2/(2/log(9/8)))-(y.^2/(2/log(9/8)))))+20;
meshc(x,y,z)
hold on
[x,y]=meshgrid(3:0.01:6);
z=170*exp(-(((x-5).^2/(2/log(9/8)))-((y-3).^2/(2/log(9/8)))))+20;
meshc(x,y,z)
hold on
[x,y]=meshgrid(0:0.01:6);
z=180*exp(-((x.^2/(2/log(9/8)))-((y-3).^2/(2/log(9/8)))))+20;
meshc(x,y,z)
hold on
[x,y]=meshgrid(0:0.01:6);
z=40*exp(-(((x-5).^2/(2/log(9/8)))-(y.^2/(2/log(9/8)))))+20;
%meshc(x,y,z)
mesh(x,y,z)
figure
contour(x,y,z)

