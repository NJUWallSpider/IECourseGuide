        [x,y,z]=peaks(20);
        [dx,dy]=gradient(z,.5,.5);
        contour(x,y,z,10)
        hold  on
        quiver(x,y,dx,dy)
        hold off