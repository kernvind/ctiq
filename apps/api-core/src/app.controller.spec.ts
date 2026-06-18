import { Test, TestingModule } from '@nestjs/testing';
import { AppController } from './app.controller';
import { AppService } from './app.service';

describe('AppController', () => {
  let appController: AppController;

  beforeEach(async () => {
    const app: TestingModule = await Test.createTestingModule({
      controllers: [AppController],
      providers: [
        // AppService.getHello() pings the DB; mock it so this stays a pure unit test.
        {
          provide: AppService,
          useValue: { getHello: jest.fn().mockResolvedValue('ok') },
        },
      ],
    }).compile();

    appController = app.get<AppController>(AppController);
  });

  describe('root', () => {
    it('returns the health string', async () => {
      await expect(appController.getHello()).resolves.toBe('ok');
    });
  });
});
