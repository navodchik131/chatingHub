import { Alert } from 'react-native';

/** Показывает понятное модальное сообщение об ошибке (validation, API и т.д.). */
export function showUserError(message: string, title = 'Ошибка') {
  const text = (message || '').trim();
  if (!text) return;
  Alert.alert(title, text, [{ text: 'OK' }]);
}

/** Информационное сообщение — сохранено, отправлено и т.п. */
export function showUserInfo(message: string, title = 'Готово') {
  const text = (message || '').trim();
  if (!text) return;
  Alert.alert(title, text, [{ text: 'OK' }]);
}
