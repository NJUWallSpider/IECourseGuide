[x,y,z]=peaks(30);
surf(x,y,z)
axis([-3 3 -3 3 -10 10])
%axis off
%shading interp
%colormap(hot)
m=moviein(15);
for i=1:15
   view(-37.5+24*(i-1),30)
   m(:,i)=getframe;
end
movie(m)