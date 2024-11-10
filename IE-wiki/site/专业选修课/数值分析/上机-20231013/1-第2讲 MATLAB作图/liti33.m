subplot(2,2,1);fplot('hump',[0,1])
subplot(2,2,2);fplot('abs(exp(-j*x*(0:9))*ones(10,1))',[0 2*pi])
subplot(2,2,3);fplot('[tanh(x),sin(x),cos(x)]',2*pi*[-1 1 -1 1])
subplot(2,2,4);fplot('sin(1./x)',[0.001 0.1],1e-3)