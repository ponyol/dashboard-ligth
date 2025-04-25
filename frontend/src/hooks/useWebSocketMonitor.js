import { useState, useEffect, useRef } from 'react';

export default function useWebSocketMonitor(socket) {
  const [isConnected, setIsConnected] = useState(false);
  const [messagesReceived, setMessagesReceived] = useState(0);
  const [messagesSent, setMessagesSent] = useState(0);
  const [errors, setErrors] = useState([]);
  const [disconnects, setDisconnects] = useState(0);
  const socketRef = useRef(socket);

  useEffect(() => {
    if (!socketRef.current) return;

    const handleOpen = () => {
      setIsConnected(true);
    };

    const handleMessage = () => {
      setMessagesReceived((prev) => prev + 1);
    };

    const handleError = (event) => {
      setErrors((prev) => [...prev, event.error]);
    };

    const handleClose = () => {
      setIsConnected(false);
      setDisconnects((prev) => prev + 1);
    };

    socketRef.current.addEventListener('open', handleOpen);
    socketRef.current.addEventListener('message', handleMessage);
    socketRef.current.addEventListener('error', handleError);
    socketRef.current.addEventListener('close', handleClose);

    return () => {
      socketRef.current.removeEventListener('open', handleOpen);
      socketRef.current.removeEventListener('message', handleMessage);
      socketRef.current.removeEventListener('error', handleError);
      socketRef.current.removeEventListener('close', handleClose);
    };
  }, [socketRef]);

  const sendMessage = (message) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(message);
      setMessagesSent((prev) => prev + 1);
    }
  };

  return {
    isConnected,
    messagesReceived,
    messagesSent,
    errors,
    disconnects,
    sendMessage
  };
}