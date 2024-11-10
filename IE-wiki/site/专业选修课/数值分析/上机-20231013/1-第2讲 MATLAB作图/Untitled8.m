[x,y]=meshgrid(0:0.01:4);
z=9/8*exp(-(x.^2/2))+20;
meshc(x,y,z)
hold on
[x,y]=meshgrid(0:0.01:4);
z=9/8*exp(-((x-4).^2/2))+20;
meshc(x,y,z)
hold on
[x,y]=meshgrid(0:0.01:4);
z=9/8*exp(-(y.^2))+20;
meshc(x,y,z)
hold on
[x,y]=meshgrid(0:0.01:4);
z=9/8*exp(-((y-4).^2/2))+20;
meshc(x,y,z)
